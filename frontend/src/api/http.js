import axios from "axios"
import { isAuditActive, recordAuditEvent } from "./idleAudit.js"

const defaultBaseURL = typeof window !== "undefined" && window.location?.origin
  ? window.location.origin
  : "http://127.0.0.1:16888"

const http = axios.create({
  baseURL: defaultBaseURL,
  timeout: 30000,
})

// Request interceptor: timing and opt-in idle network audit
http.interceptors.request.use((config) => {
  config._startTime = Date.now()

  if (isAuditActive()) {
    recordAuditEvent({
      kind: "http_request",
      originComponent: config.headers?.["X-Component-Origin"] || "http_client",
      eventOrEffectName: config.headers?.["X-Effect-Name"] || "api_call",
      userIntentId: config.headers?.["X-User-Intent-ID"] || null,
      correlationId: config.headers?.["X-Correlation-ID"] || null,
      route: config.url || "/",
      method: (config.method || "GET").toUpperCase(),
      destination: config.url || "/",
      outcome: "dispatched",
    })
  }

  return config
})

// Response interceptor: timing, error logging, and audit
http.interceptors.response.use(
  (res) => {
    const durationMs = Date.now() - (res.config._startTime || Date.now())
    if (isAuditActive()) {
      recordAuditEvent({
        kind: "http_response",
        originComponent: res.config.headers?.["X-Component-Origin"] || "http_client",
        eventOrEffectName: res.config.headers?.["X-Effect-Name"] || "api_call",
        userIntentId: res.config.headers?.["X-User-Intent-ID"] || null,
        correlationId: res.config.headers?.["X-Correlation-ID"] || null,
        route: res.config.url || "/",
        method: (res.config.method || "GET").toUpperCase(),
        destination: res.config.url || "/",
        outcome: res.status,
        durationMs,
      })
    }
    return res
  },
  (err) => {
    const durationMs = Date.now() - (err.config?._startTime || Date.now())
    if (isAuditActive() && err.config) {
      recordAuditEvent({
        kind: "http_response",
        originComponent: err.config.headers?.["X-Component-Origin"] || "http_client",
        eventOrEffectName: err.config.headers?.["X-Effect-Name"] || "api_call",
        userIntentId: err.config.headers?.["X-User-Intent-ID"] || null,
        correlationId: err.config.headers?.["X-Correlation-ID"] || null,
        route: err.config.url || "/",
        method: (err.config.method || "GET").toUpperCase(),
        destination: err.config.url || "/",
        outcome: err.response?.status || "error",
        durationMs,
      })
    }
    if (axios.isCancel(err) || err?.code === "ERR_CANCELED" || err?.message === "canceled") {
      return Promise.reject(err)
    }
    console.error("API error:", err.response?.data || err.message)
    return Promise.reject(err)
  }
)

export default http
