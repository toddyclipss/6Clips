// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors

/**
 * Native Motion Spec UI Adapter (native_motion_v1).
 *
 * Provides a typed bridge between the authoritative backend native_motion_v1 schema
 * and the canonical frontend player/timeline workspaces.
 *
 * Guarantees seamless dual-mode rendering:
 * 1. Legacy saved-project documents with document.timeline.tracks
 * 2. Newly generated native_motion_v1 projects with composition operators & typed tracks
 */

export const NATIVE_MOTION_SCHEMA_VERSION = "native_motion_v1"

export const CANONICAL_TRACK_TYPES = Object.freeze([
  "video",
  "audio",
  "captions",
  "effects",
  "transitions",
])

export const TRACK_DROP_PERMISSIONS = Object.freeze({
  video: Object.freeze(["video", "image", "media"]),
  audio: Object.freeze(["audio", "music", "voiceover", "sfx"]),
  captions: Object.freeze(["captions", "caption", "text", "typography", "subtitle"]),
  effects: Object.freeze(["effect", "filter", "shader", "motion_operator"]),
  transitions: Object.freeze(["transition", "dissolve", "wipe", "crossfade"]),
})

/**
 * Checks whether a given project or document conforms to the native_motion_v1 specification.
 *
 * @param {object|null|undefined} docOrProject
 * @returns {boolean}
 */
export function isNativeMotionV1(docOrProject) {
  if (!docOrProject || typeof docOrProject !== "object") return false
  const target = docOrProject.document || docOrProject
  if (target.schema_version === NATIVE_MOTION_SCHEMA_VERSION) return true
  if (target.spec_version === NATIVE_MOTION_SCHEMA_VERSION) return true
  if (target.format === NATIVE_MOTION_SCHEMA_VERSION) return true
  if (target.editor_mode === "native_motion" || target.editor_mode === "native_motion_v1") return true
  if (Boolean(target.native_motion_v1)) return true
  if (Array.isArray(target?.composition?.operators)) return true
  if (Array.isArray(target?.scenes) && target?.scenes.length > 0) return true
  return false
}

/**
 * Validates whether a dragged clip item can be dropped onto a target track.
 * Enforces strict content-safety boundaries:
 * - Captions/text cannot be dropped onto audio tracks
 * - Audio cannot be dropped onto video or captions tracks
 * - Video/image cannot be dropped onto audio or captions tracks
 * - Effects/transitions cannot be dropped onto audio or captions tracks
 * - Locked tracks always reject drops
 *
/**
 * Validates whether a dragged clip/asset can be legally dropped onto a target timeline track.
 * Enforces strict content safety drop boundaries (e.g. captions cannot be dropped on audio tracks).
 *
 * @param {object} clip
 * @param {object|string} targetTrack
 * @returns {{ valid: boolean, reason?: string }}
 */
export function validateTrackDrop(clip, targetTrack) {
  if (!clip || !targetTrack) {
    return { valid: false, reason: "Invalid clip or track reference" }
  }
  const trackObj = typeof targetTrack === "string" ? { type: targetTrack } : targetTrack
  if (trackObj.locked) {
    return { valid: false, reason: `Track "${trackObj.name || trackObj.id}" is locked` }
  }

  const trackType = (trackObj.type || "").toLowerCase()
  if (!TRACK_DROP_PERMISSIONS[trackType]) {
    return { valid: false, reason: `Unknown or unsupported track type: ${trackType}` }
  }

  const rawClipType = (clip.type || clip.mediaType || clip.kind || "").toLowerCase()

  // Identify clip category
  let clipCategory = "video"
  if (rawClipType === "audio" || rawClipType === "voiceover" || Boolean(clip.audio_file)) {
    clipCategory = "audio"
  } else if (rawClipType === "captions" || rawClipType === "caption" || rawClipType === "text" || Boolean(clip.caption_text)) {
    clipCategory = "captions"
  } else if (rawClipType === "effect" || rawClipType === "filter" || rawClipType === "shader") {
    clipCategory = "effects"
  } else if (rawClipType === "transition") {
    clipCategory = "transitions"
  } else if (rawClipType === "image" || rawClipType === "video" || rawClipType === "media" || rawClipType === "broll") {
    clipCategory = "video"
  }

  const allowedTypes = TRACK_DROP_PERMISSIONS[trackType]
  const isAllowed = allowedTypes.includes(clipCategory) || allowedTypes.includes(rawClipType)

  if (!isAllowed) {
    return {
      valid: false,
      reason: `Cannot drop ${clipCategory} clip onto ${trackType} track: track boundaries enforce content safety.`,
    }
  }

  return { valid: true }
}

/**
 * Normalizes any project or document (legacy or native_motion_v1) into a canonical
 * representation suitable for the single player and canonical timeline.
 *
 * @param {object|null|undefined} projectOrDoc
 * @returns {{
 *   isNativeMotion: boolean,
 *   tracks: Array<object>,
 *   duration: number,
 *   fps: number,
 *   aspectRatio: string,
 *   schemaVersion: string
 * }}
 */
export function normalizeProjectForPlayer(projectOrDoc) {
  if (!projectOrDoc || typeof projectOrDoc !== "object") {
    return {
      isNativeMotion: false,
      tracks: [],
      duration: 0,
      fps: 30,
      aspectRatio: "9:16",
      schemaVersion: "legacy",
    }
  }

  const doc = projectOrDoc.document || projectOrDoc
  const isNative = isNativeMotionV1(doc)

  const probeDuration = Number(
    projectOrDoc.media_probe?.duration_seconds ??
    doc.media_probe?.duration_seconds
  )
  const duration = Number.isFinite(probeDuration) && probeDuration > 0
    ? probeDuration
    : Number(
        doc.duration_seconds ??
        doc.duration ??
        doc.timeline?.duration_seconds ??
        projectOrDoc.duration_seconds ??
        projectOrDoc.duration ??
        0
      )
  const fps = Number(doc.fps || doc.timeline?.fps || 30)
  const aspectRatio = doc.aspect_ratio || doc.aspectRatio || projectOrDoc.aspect_ratio || projectOrDoc.aspectRatio || "9:16"

  // If already has canonical timeline tracks, ensure all clips have expected fields
  if (Array.isArray(doc.timeline?.tracks)) {
    const sanitizedTracks = doc.timeline.tracks.map((track, tIdx) => ({
      id: track.id || `track_${tIdx + 1}`,
      name: track.name || `Track ${tIdx + 1}`,
      type: track.type || (tIdx === 1 ? "audio" : "video"),
      visible: track.visible !== false,
      locked: Boolean(track.locked),
      muted: Boolean(track.muted),
      solo: Boolean(track.solo),
      clips: (track.clips || []).map((c, cIdx) => ({
        id: c.id || `clip_${tIdx}_${cIdx}`,
        name: c.name || c.title || `Clip ${cIdx + 1}`,
        type: c.type || track.type || "video",
        start_seconds: Number(c.start_seconds || 0),
        duration_seconds: Math.max(0.1, Number(c.duration_seconds || 1.0)),
        trim_start: Number(c.trim_start || 0),
        trim_end: Number(c.trim_end || c.duration_seconds || 1.0),
        speed: Number(c.speed || 1.0),
        volume: Number(c.volume ?? 1.0),
        caption_text: c.caption_text || "",
        asset_id: c.asset_id || null,
        asset_file: c.asset_file || null,
        src: c.src || c.asset_file || null,
        properties: c.properties || {},
      })),
    }))

    return {
      isNativeMotion: isNative,
      tracks: sanitizedTracks,
      duration,
      fps,
      aspectRatio,
      aspect_ratio: aspectRatio,
      schemaVersion: isNative ? NATIVE_MOTION_SCHEMA_VERSION : (doc.schema_version || "legacy"),
    }
  }

  // If native_motion_v1 with composition operators or layers, adapt to canonical tracks
  const rawOperators = doc.operators || doc.composition?.operators
  if (isNative && Array.isArray(rawOperators)) {
    const videoClips = []
    const audioClips = []
    const captionClips = []
    const effectClips = []
    const transitionClips = []

    rawOperators.forEach((op, idx) => {
      const clipId = op.id || `op_${idx + 1}`
      const baseClip = {
        id: clipId,
        name: op.label || op.operator || op.name || `Motion ${idx + 1}`,
        type: op.type || op.operator || "video",
        start_seconds: Number(op.start_time ?? op.time_offset ?? op.start_seconds ?? 0),
        duration_seconds: Number(op.duration ?? op.duration_seconds ?? 3),
        trim_start: 0,
        trim_end: Number(op.duration ?? op.duration_seconds ?? 3),
        speed: 1.0,
        volume: 1.0,
        src: op.src || op.asset_file || op.audio_file || null,
        text: op.text || op.caption_text || op.params?.text || "",
        properties: op.params || op.properties || {},
      }

      const opType = (op.type || op.operator || "").toLowerCase()
      if (opType === "caption" || opType === "captions" || opType === "text" || Boolean(op.caption_text)) {
        captionClips.push({ ...baseClip, type: "captions", caption_text: baseClip.text || op.caption_text })
      } else if (opType === "audio" || opType === "speech" || opType === "voiceover" || op.audio_file) {
        audioClips.push({ ...baseClip, type: "audio" })
      } else if (opType === "effect" || opType === "filter") {
        effectClips.push({ ...baseClip, type: "effects" })
      } else if (opType === "transition") {
        transitionClips.push({ ...baseClip, type: "transitions" })
      } else {
        videoClips.push({ ...baseClip, type: "video" })
      }
    })

    const tracks = [
      { id: "track-video", name: "Video", type: "video", visible: true, locked: false, clips: videoClips },
      { id: "track-audio", name: "Audio", type: "audio", visible: true, locked: false, clips: audioClips },
      { id: "track-captions", name: "Captions", type: "captions", visible: true, locked: false, clips: captionClips },
      { id: "track-effects", name: "Effects", type: "effects", visible: true, locked: false, clips: effectClips },
      { id: "track-transitions", name: "Transitions", type: "transitions", visible: true, locked: false, clips: transitionClips },
    ]

    return {
      isNativeMotion: true,
      tracks,
      duration,
      fps,
      aspectRatio,
      aspect_ratio: aspectRatio,
      schemaVersion: NATIVE_MOTION_SCHEMA_VERSION,
    }
  }

  // If native_motion_v1 with scene graph specification (scenes & captions)
  if (isNative && Array.isArray(doc.scenes)) {
    const videoClips = []
    const audioClips = []
    const captionClips = []
    const effectClips = []
    const transitionClips = []

    doc.scenes.forEach((scene, sIdx) => {
      const sceneStart = Number(scene.timecode_start ?? (sIdx * 3))
      const sceneEnd = Number(scene.timecode_end ?? (sceneStart + 3))
      const sceneDur = Math.max(0.5, sceneEnd - sceneStart)

      const elements = Array.isArray(scene.elements) ? scene.elements : []
      elements.forEach((el, eIdx) => {
        const elType = (el.element_type || el.type || "text").toLowerCase()
        const elStart = sceneStart + Number(el.start_time ?? 0)
        const elDur = Number(el.duration ?? sceneDur)
        const clipItem = {
          id: el.element_id || `scene_${sIdx}_el_${eIdx}`,
          name: el.properties?.title || el.properties?.text || `${elType} (Scene ${scene.scene_number || sIdx + 1})`,
          type: elType,
          start_seconds: elStart,
          duration_seconds: elDur,
          trim_start: 0,
          trim_end: elDur,
          speed: 1.0,
          volume: 1.0,
          caption_text: el.properties?.text || "",
          properties: el.properties || {},
          keyframes: el.keyframes || [],
        }

        if (["audio", "voiceover", "music", "sfx", "speech"].includes(elType)) {
          audioClips.push({ ...clipItem, type: "audio" })
        } else if (["captions", "caption"].includes(elType)) {
          captionClips.push({ ...clipItem, type: "captions" })
        } else if (["effect", "filter", "shader"].includes(elType)) {
          effectClips.push({ ...clipItem, type: "effects" })
        } else if (["transition"].includes(elType)) {
          transitionClips.push({ ...clipItem, type: "transitions" })
        } else {
          videoClips.push({ ...clipItem, type: "video" })
        }
      })
    })

    // Integrate document-level captions if provided
    if (Array.isArray(doc.captions) && doc.captions.length > 0) {
      doc.captions.forEach((cap, cIdx) => {
        const capStart = Number(cap.start_time ?? cap.start ?? 0)
        const capEnd = Number(cap.end_time ?? cap.end ?? (capStart + 2.5))
        captionClips.push({
          id: cap.id || `cap_${cIdx + 1}`,
          name: cap.text ? (cap.text.slice(0, 30) + (cap.text.length > 30 ? "..." : "")) : `Caption ${cIdx + 1}`,
          type: "captions",
          start_seconds: capStart,
          duration_seconds: Math.max(0.2, capEnd - capStart),
          trim_start: 0,
          trim_end: Math.max(0.2, capEnd - capStart),
          speed: 1.0,
          volume: 1.0,
          caption_text: cap.text || "",
          words: cap.words || [],
          properties: cap,
        })
      })
    }

    const tracks = [
      { id: "track-video", name: "Visual Scenes", type: "video", visible: true, locked: false, clips: videoClips },
      { id: "track-audio", name: "Audio", type: "audio", visible: true, locked: false, clips: audioClips },
      { id: "track-captions", name: "Captions", type: "captions", visible: true, locked: false, clips: captionClips },
      { id: "track-effects", name: "Effects", type: "effects", visible: true, locked: false, clips: effectClips },
      { id: "track-transitions", name: "Transitions", type: "transitions", visible: true, locked: false, clips: transitionClips },
    ]

    const effectiveDuration = Number(doc.target_duration_sec || duration || (doc.scenes.length * 3))

    return {
      isNativeMotion: true,
      tracks,
      duration: effectiveDuration,
      fps,
      aspectRatio,
      aspect_ratio: aspectRatio,
      schemaVersion: NATIVE_MOTION_SCHEMA_VERSION,
    }
  }

  // Fallback: flat clips list
  const flatClips = Array.isArray(doc.clips) ? doc.clips : []
  const defaultTracks = [
    {
      id: "track_1",
      name: "Video 1",
      type: "video",
      visible: true,
      locked: false,
      clips: flatClips.map((c, i) => ({
        id: c.id || `clip_${i}`,
        name: c.name || `Clip ${i + 1}`,
        type: "video",
        start_seconds: Number(c.start_seconds || 0),
        duration_seconds: Number(c.duration_seconds || 3),
        trim_start: Number(c.trim_start || 0),
        trim_end: Number(c.trim_end || c.duration_seconds || 3),
        speed: Number(c.speed || 1.0),
        volume: 1.0,
        caption_text: "",
        properties: {},
      })),
    },
    { id: "track_2", name: "Audio 1", type: "audio", visible: true, locked: false, clips: [] },
    { id: "track_3", name: "Captions", type: "captions", visible: true, locked: false, clips: [] },
  ]

  return {
    isNativeMotion: isNative,
    tracks: defaultTracks,
    duration,
    fps,
    aspectRatio,
    schemaVersion: "legacy_flat",
  }
}
