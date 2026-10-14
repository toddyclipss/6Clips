import { isAuditActive, recordAuditEvent } from "./idleAudit.js"

const WS_PROTOCOL = typeof window !== "undefined" && window.location?.protocol === "https:" ? "wss:" : "ws:"
const WS_HOST = typeof window !== "undefined" && window.location?.host ? window.location.host : "127.0.0.1:16888"
const WS_URL = `${WS_PROTOCOL}//${WS_HOST}/ws/chat`

const MAX_QUEUE_TTL_MS = 15000 // Expire disconnected queue messages after 15s to prevent replay

class ViralMintWS {
  constructor() {
    this.ws = null
    this.listeners = {}
    this.reconnectDelay = 1000
    this.maxReconnectDelay = 30000
    this._shouldReconnect = true
    this._queue = [] // messages queued while disconnected
  }

  get connected() {
    return this.ws?.readyState === WebSocket.OPEN
  }

  connect() {
    // Guard BOTH open and still-CONNECTING sockets. connect() is called on
    // every Layout mount — React StrictMode double-invokes that effect, and
    // the second call used to land while the first socket was still
    // CONNECTING, creating a SECOND WebSocket without closing the first.
    // Both sockets then fed the same listener set, so every server event was
    // handled twice: duplicate chat bubbles, doubled streaming text, and
    // duplicate job cards.
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return
    }

    if (isAuditActive()) {
      recordAuditEvent({
        kind: "ws_connect",
        originComponent: "websocket_client",
        eventOrEffectName: "connect",
        route: "/ws/chat",
        destination: WS_URL,
        method: "CONNECT",
        outcome: "initiating",
      })
    }

    // Capture the socket in a local: every handler below compares it against
    // `this.ws` so a SUPERSEDED socket goes silent instead of racing the
    // current one.
    const socket = new WebSocket(WS_URL)
    this.ws = socket

    socket.onmessage = (e) => {
      // A superseded socket must go silent even if it lingers half-open.
      if (this.ws !== socket) return
      try {
        const msg = JSON.parse(e.data)

        if (isAuditActive()) {
          recordAuditEvent({
            kind: "ws_message",
            originComponent: "websocket_client",
            eventOrEffectName: "onmessage",
            route: "/ws/chat",
            destination: WS_URL,
            method: "RECV",
            outcome: msg.type || "unknown",
            extra: { msg_type: msg.type },
          })
        }

        const handlers = this.listeners[msg.type] || []
        handlers.forEach(h => h(msg))
      } catch (err) {
        console.error("WS parse error:", err)
      }
    }

    socket.onclose = () => {
      // Only the CURRENT socket drives connection state + reconnect; a stale
      // socket closing must not trigger a parallel reconnect loop.
      if (this.ws !== socket) return

      // Notify listeners of disconnection
      const handlers = this.listeners["_connection_state"] || []
      handlers.forEach(h => h({ connected: false }))

      if (this._shouldReconnect) {
        setTimeout(() => this.connect(), this.reconnectDelay)
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
      }
    }

    socket.onopen = () => {
      if (this.ws !== socket) {
        // Superseded while connecting — close it so it can't double-deliver.
        try { socket.close() } catch { /* already closing */ }
        return
      }
      this.reconnectDelay = 1000

      // Flush queued messages with TTL and deduplication safety
      const now = Date.now()
      const pending = this._queue.splice(0)
      for (const msg of pending) {
        // Drop expired offline chat messages so offline reconnect never launches surprise inference
        if (msg.type === "chat_message" && msg.queued_at && (now - msg.queued_at > MAX_QUEUE_TTL_MS)) {
          console.warn("[WS] Dropped expired offline chat message to prevent unauthorized inference replay")
          continue
        }

        if (isAuditActive()) {
          recordAuditEvent({
            kind: "ws_send",
            originComponent: "websocket_client",
            eventOrEffectName: "flush_queued_onopen",
            userIntentId: msg.user_intent_id || null,
            route: "/ws/chat",
            destination: WS_URL,
            method: "SEND",
            outcome: "flushed",
            extra: { msg_type: msg.type },
          })
        }

        socket.send(JSON.stringify(msg))
      }

      // Notify listeners of connection
      const handlers = this.listeners["_connection_state"] || []
      handlers.forEach(h => h({ connected: true }))
    }

    socket.onerror = (err) => {
      if (this.ws !== socket) return
      console.error("WS error:", err)
    }
  }

  on(type, callback) {
    if (!this.listeners[type]) this.listeners[type] = []
    this.listeners[type].push(callback)
    return () => {
      this.listeners[type] = this.listeners[type].filter(h => h !== callback)
    }
  }

  send(message) {
    if (message && typeof message === "object" && message.type === "chat_message") {
      if (!message.user_intent_id) {
        message.user_intent_id = `intent_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
      }
      message.queued_at = Date.now()
    }

    if (this.ws?.readyState === WebSocket.OPEN) {
      if (isAuditActive()) {
        recordAuditEvent({
          kind: "ws_send",
          originComponent: "websocket_client",
          eventOrEffectName: "send_live",
          userIntentId: message.user_intent_id || null,
          route: "/ws/chat",
          destination: WS_URL,
          method: "SEND",
          outcome: "dispatched",
          extra: { msg_type: message.type },
        })
      }
      this.ws.send(JSON.stringify(message))
    } else {
      // Queue important messages (chat, wizard steps) for retry on reconnect
      const queueable = ["chat_message", "set_session", "wizard_step_complete", "wizard_cancel"]
      if (queueable.includes(message.type)) {
        // Deduplicate set_session messages while offline (only latest session is relevant)
        if (message.type === "set_session") {
          this._queue = this._queue.filter(m => m.type !== "set_session")
        }
        this._queue.push(message)
      }
    }
  }

  disconnect() {
    this._shouldReconnect = false
    this.ws?.close()
  }

}

export const ws = new ViralMintWS()
