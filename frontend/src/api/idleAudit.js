// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Centralized Dev-Only Opt-In Idle Network Audit for 6Clips Frontend.
 * Active only when SIXCLIPS_IDLE_NET_AUDIT=1 or window.__SIXCLIPS_IDLE_NET_AUDIT is set.
 * Captures metadata-only traces without prompt content, user text, tokens, or media bytes.
 * Writes sanitized records to %TEMP%\6clips_wave12_idle_audit\ if running in supported environment.
 */

const MAX_AUDIT_LOG_SIZE = 1000

// Internal in-memory ring buffer
const _auditLog = []

/**
 * Check if audit tracing is actively enabled
 */
export function isAuditActive() {
  if (typeof process !== "undefined" && process.env?.SIXCLIPS_IDLE_NET_AUDIT === "1") {
    return true
  }
  if (typeof window !== "undefined") {
    if (window.__SIXCLIPS_IDLE_NET_AUDIT === true || window.__SIXCLIPS_IDLE_NET_AUDIT === "1") {
      return true
    }
    try {
      if (window.localStorage && window.localStorage.getItem("SIXCLIPS_IDLE_NET_AUDIT") === "1") {
        return true
      }
    } catch {}
  }
  return false
}

/**
 * Enable or disable audit tracing at runtime
 */
export function setAuditActive(active) {
  if (typeof window !== "undefined") {
    window.__SIXCLIPS_IDLE_NET_AUDIT = Boolean(active)
    try {
      if (window.localStorage) {
        if (active) window.localStorage.setItem("SIXCLIPS_IDLE_NET_AUDIT", "1")
        else window.localStorage.removeItem("SIXCLIPS_IDLE_NET_AUDIT")
      }
    } catch {}
  }
  if (typeof process !== "undefined" && process.env) {
    process.env.SIXCLIPS_IDLE_NET_AUDIT = active ? "1" : "0"
  }
}

/**
 * Sanitize destination URL: strip query parameters, auth tokens, and credentials.
 */
export function sanitizeDestination(rawUrl) {
  if (!rawUrl || typeof rawUrl !== "string") return "unknown"
  try {
    const parsed = new URL(rawUrl, typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:16888")
    return `${parsed.protocol}//${parsed.host}${parsed.pathname}`
  } catch {
    return rawUrl.split("?")[0].split("#")[0]
  }
}

/**
 * Classify endpoint into standardized contract categories
 */
export function classifyEndpoint(destination, method = "GET", userIntentId = null) {
  const sanitized = sanitizeDestination(destination)
  const isPostOrPut = method === "POST" || method === "PUT"

  // Check external domains
  const isLocal = sanitized.includes("localhost") || sanitized.includes("127.0.0.1") || sanitized.startsWith("/")
  if (!isLocal) {
    if (sanitized.includes("youtube.com") || sanitized.includes("ytimg.com")) {
      return "READ_ONLY_HEALTH_DISCOVERY"
    }
    return "UNSOLICITED_EXTERNAL_EGRESS"
  }

  // Generative / inference routes
  const isGenerative = (
    sanitized.includes("/api/chat") ||
    sanitized.includes("/api/generate") ||
    sanitized.includes("/api/downloaded/polish-script") ||
    sanitized.includes("/api/downloaded/generate-script") ||
    sanitized.includes("/api/tools/transcribe") ||
    sanitized.includes("/api/tools/voiceover") ||
    sanitized.includes("/api/tools/translate") ||
    sanitized.includes("chat_message")
  )

  if (isGenerative) {
    if (userIntentId) {
      return "USER_AUTHORIZED"
    }
    return "UNSOLICITED_INFERENCE"
  }

  // Read-only discovery and health routes
  if (
    sanitized.includes("/api/config/model_registry") ||
    sanitized.includes("/api/settings/health") ||
    sanitized.includes("/api/settings/motion-graphics/status") ||
    sanitized.includes("/api/catalog/") ||
    sanitized.includes("/api/projects/catalog/") ||
    sanitized.includes("/api/jobs") ||
    sanitized.includes("/api/settings") ||
    sanitized.includes("/api/trends/results") ||
    sanitized.includes("/api/library/") ||
    sanitized.includes("/ws/chat")
  ) {
    return userIntentId ? "USER_AUTHORIZED" : "READ_ONLY_HEALTH_DISCOVERY"
  }

  if (userIntentId) return "USER_AUTHORIZED"
  return isPostOrPut ? "USER_AUTHORIZED" : "READ_ONLY_HEALTH_DISCOVERY"
}

/**
 * Record a sanitized audit event
 */
export function recordAuditEvent({
  kind = "http_request",
  originComponent = "unknown",
  eventOrEffectName = "unknown",
  userIntentId = null,
  correlationId = null,
  route = "/",
  method = "GET",
  destination = "",
  outcome = "pending",
  durationMs = 0,
  extra = {},
}) {
  if (!isAuditActive()) return

  const sanitized = sanitizeDestination(destination || route)
  const endpointClass = classifyEndpoint(sanitized, method, userIntentId)

  const record = {
    t: new Date().toISOString(),
    kind,
    origin_component: originComponent,
    event_or_effect_name: eventOrEffectName,
    user_intent_id: userIntentId || null,
    correlation_id: correlationId || (typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : `cid_${Date.now()}`),
    route: route || "/",
    method: method.toUpperCase(),
    sanitized_destination: sanitized,
    endpoint_class: endpointClass,
    trigger_authorization: userIntentId ? "USER_AUTHORIZED" : (endpointClass === "READ_ONLY_HEALTH_DISCOVERY" ? "READ_ONLY_HEALTH_DISCOVERY" : "UNSOLICITED"),
    outcome: String(outcome),
    duration_ms: Math.round(durationMs || 0),
  }

  if (_auditLog.length >= MAX_AUDIT_LOG_SIZE) {
    _auditLog.shift()
  }
  _auditLog.push(record)

  // In Node / CLI test runner environments, flush to %TEMP%/6clips_wave12_idle_audit if accessible
  try {
    if (typeof process !== "undefined" && process.env?.TEMP) {
      const fs = globalThis.fs || (typeof require !== "undefined" ? require("fs") : null)
      const path = globalThis.path || (typeof require !== "undefined" ? require("path") : null)
      if (fs && path) {
        const auditDir = path.join(process.env.TEMP, "6clips_wave12_idle_audit")
        if (!fs.existsSync(auditDir)) {
          fs.mkdirSync(auditDir, { recursive: true })
        }
        const filePath = path.join(auditDir, "frontend_idle_audit.jsonl")
        fs.appendFileSync(filePath, JSON.stringify(record) + "\n", "utf8")
      }
    }
  } catch {}

  return record
}

/**
 * Retrieve current in-memory audit log
 */
export function getAuditLog() {
  return [..._auditLog]
}

/**
 * Clear current in-memory audit log
 */
export function clearAuditLog() {
  _auditLog.length = 0
}

/**
 * Compute counts by endpoint class and kind
 */
export function getAuditSummary() {
  const summary = {
    total: _auditLog.length,
    by_endpoint_class: {},
    by_kind: {},
    unsolicited_inference_count: 0,
    unsolicited_external_egress_count: 0,
  }

  for (const item of _auditLog) {
    summary.by_endpoint_class[item.endpoint_class] = (summary.by_endpoint_class[item.endpoint_class] || 0) + 1
    summary.by_kind[item.kind] = (summary.by_kind[item.kind] || 0) + 1
    if (item.endpoint_class === "UNSOLICITED_INFERENCE") {
      summary.unsolicited_inference_count++
    }
    if (item.endpoint_class === "UNSOLICITED_EXTERNAL_EGRESS") {
      summary.unsolicited_external_egress_count++
    }
  }

  return summary
}
