import { lazy, Suspense } from "react"
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom"
import { Snackbar, Alert, Button, CircularProgress, Box } from "@mui/material"
import ErrorBoundary from "./components/ErrorBoundary"
import Layout from "./components/Layout"
import useAppStore from "./store/appStore"
import { pluginRoutes } from "./plugins"

// Route-level code splitting
const Trends = lazy(() => import("./pages/Trends"))
const Settings = lazy(() => import("./pages/Settings"))
const Library = lazy(() => import("./pages/Library"))
const Channels = lazy(() => import("./pages/Channels"))
const Messaging = lazy(() => import("./pages/Messaging"))
const ClipStudio = lazy(() => import("./pages/ClipStudio"))
const MotionGraphics = lazy(() => import("./pages/MotionGraphics"))
const Catalog = lazy(() => import("./pages/Catalog"))
const Distribution = lazy(() => import("./pages/Distribution"))
const Analytics = lazy(() => import("./pages/Analytics"))
const Tools = lazy(() => import("./pages/Tools"))

// Tools — single-purpose utility pages. Each is a thin wrapper around the
// shared ToolRunner; lazy-loaded so the bundle for the hub stays small.
const ToolCaptions = lazy(() => import("./pages/tools/Captions"))
const ToolReframe = lazy(() => import("./pages/tools/Reframe"))
const ToolAudioEnhance = lazy(() => import("./pages/tools/AudioEnhance"))
const ToolWatermark = lazy(() => import("./pages/tools/Watermark"))
const ToolRemoveSilence = lazy(() => import("./pages/tools/RemoveSilence"))
const ToolMergeClips = lazy(() => import("./pages/tools/MergeClips"))
const ToolGif = lazy(() => import("./pages/tools/Gif"))
const ToolSpeed = lazy(() => import("./pages/tools/Speed"))
const ToolTrim = lazy(() => import("./pages/tools/Trim"))
const ToolSubtitles = lazy(() => import("./pages/tools/Subtitles"))
const ToolAutoZoom = lazy(() => import("./pages/tools/AutoZoom"))
const ToolTransform = lazy(() => import("./pages/tools/Transform"))
const ToolMusicVisualizer = lazy(() => import("./pages/tools/MusicVisualizer"))
const ToolVoiceover = lazy(() => import("./pages/tools/Voiceover"))
const ToolHookAnalysis = lazy(() => import("./pages/tools/HookAnalysis"))
const ToolTranslate = lazy(() => import("./pages/tools/Translate"))
const ToolMetadata = lazy(() => import("./pages/tools/Metadata"))
const ToolAutoChapters = lazy(() => import("./pages/tools/AutoChapters"))
const ToolCompress = lazy(() => import("./pages/tools/Compress"))
const ToolCrop = lazy(() => import("./pages/tools/Crop"))
const ToolVideoDownload = lazy(() => import("./pages/tools/VideoDownload"))

const LazyFallback = () => (
  <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%", minHeight: 200 }}>
    <CircularProgress size={36} />
  </Box>
)

function GlobalSnackbar() {
  const snackbar = useAppStore((s) => s.snackbar)
  const closeSnackbar = useAppStore((s) => s.closeSnackbar)
  const navigate = useNavigate()

  return (
    <Snackbar
      open={snackbar.open}
      autoHideDuration={snackbar.action ? 6000 : 4000}
      onClose={closeSnackbar}
      anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
    >
      <Alert
        onClose={closeSnackbar}
        severity={snackbar.severity}
        variant="filled"
        sx={{ width: "100%", borderRadius: 2, alignItems: "center" }}
        action={snackbar.action ? (
          <Button
            color="inherit"
            size="small"
            sx={{ fontWeight: 700, whiteSpace: "nowrap" }}
            onClick={() => { navigate(snackbar.action.href); closeSnackbar() }}
          >
            {snackbar.action.label}
          </Button>
        ) : undefined}
      >
        {snackbar.message}
      </Alert>
    </Snackbar>
  )
}

function LegacyRedirect({ to, defaultQuery = {} }) {
  const location = useLocation()
  const currentParams = new URLSearchParams(location.search)
  Object.entries(defaultQuery).forEach(([k, v]) => {
    if (!currentParams.has(k)) {
      currentParams.set(k, v)
    }
  })
  const qs = currentParams.toString()
  const target = qs ? `${to}?${qs}` : to
  return <Navigate to={target} replace />
}

function MotionRouteWrapper() {
  const qp = new URLSearchParams(window.location.search)
  const review = qp.get("review")
  const jobId = qp.get("jobId") || qp.get("job_id")
  if (review && !jobId) {
    return <Navigate to={`/motion?jobId=${encodeURIComponent(review)}&mode=review`} replace />
  }
  return <MotionGraphics />
}

export default function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
        <Suspense fallback={<LazyFallback />}>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<Navigate to="/trends" replace />} />
              <Route path="chat" element={<Navigate to="/trends" replace />} />
              <Route path="dashboard" element={<Navigate to="/videos" replace />} />
              {/* `/videos` is the Library. The path is legacy and stays: it is
                  bookmarked, and every ?tab= link the old page published still
                  arrives here and is translated into the new filters. */}
              <Route path="videos" element={<Library />} />
              <Route path="library" element={<Navigate to="/videos" replace />} />
              {/* Trends leads are not files you own, so they are not the
                  Library. */}
              <Route path="trends" element={<Trends />} />
              <Route path="trend" element={<Trends />} />
              <Route path="stock" element={<Navigate to="/trends" replace />} />
              <Route path="ai-video" element={<Navigate to="/trends" replace />} />
              <Route path="avatar" element={<Navigate to="/trends" replace />} />
              <Route path="create" element={<Navigate to="/trends" replace />} />
              <Route path="cron" element={<Navigate to="/" />} />
              <Route path="clips" element={<LegacyRedirect to="/motion" defaultQuery={{ mode: "clip" }} />} />
              <Route path="motion" element={<MotionRouteWrapper />} />
              <Route path="distribution" element={<LegacyRedirect to="/channels" />} />
              <Route path="analytics" element={<LegacyRedirect to="/channels" />} />
              <Route path="catalog" element={<LegacyRedirect to="/motion" defaultQuery={{ tab: "catalog" }} />} />
              <Route path="tools" element={<LegacyRedirect to="/motion" defaultQuery={{ mode: "tools" }} />} />
              <Route path="tools/captions" element={<ToolCaptions />} />
              <Route path="tools/reframe" element={<ToolReframe />} />
              <Route path="tools/audio-enhance" element={<ToolAudioEnhance />} />
              <Route path="tools/watermark" element={<ToolWatermark />} />
              <Route path="tools/remove-silence" element={<ToolRemoveSilence />} />
              <Route path="tools/merge-clips" element={<ToolMergeClips />} />
              <Route path="tools/gif" element={<ToolGif />} />
              <Route path="tools/speed" element={<ToolSpeed />} />
              <Route path="tools/trim" element={<ToolTrim />} />
              <Route path="tools/subtitles" element={<ToolSubtitles />} />
              <Route path="tools/auto-zoom" element={<ToolAutoZoom />} />
              <Route path="tools/transform" element={<ToolTransform />} />
              <Route path="tools/compress" element={<ToolCompress />} />
              <Route path="tools/crop" element={<ToolCrop />} />
              <Route path="tools/video-download" element={<ToolVideoDownload />} />
              <Route path="tools/music-visualizer" element={<ToolMusicVisualizer />} />
              <Route path="tools/voiceover" element={<ToolVoiceover />} />
              <Route path="tools/hook-analysis" element={<ToolHookAnalysis />} />
              <Route path="tools/translate" element={<ToolTranslate />} />
              <Route path="tools/metadata" element={<ToolMetadata />} />
              <Route path="tools/auto-chapters" element={<ToolAutoChapters />} />
              <Route path="channels" element={<Channels />} />
              <Route path="messaging" element={<Messaging />} />
              <Route path="settings" element={<Settings />} />
              {pluginRoutes.map(({ path, element }) => (
                <Route key={path} path={path} element={element} />
              ))}
              <Route path="*" element={<Navigate to="/" />} />
            </Route>
          </Routes>
        </Suspense>
        <GlobalSnackbar />
      </ErrorBoundary>
    </BrowserRouter>
  )
}
