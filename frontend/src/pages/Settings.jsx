import {
  Box, Typography, Stack, Card, CardContent,
  Button, alpha, useTheme,
} from "@mui/material"
import {
  IconSettings,
  IconKey,
  IconRobot,
  IconPuzzle,
  IconActivity,
} from "@tabler/icons-react"
import HealthDashboard from "../components/settings/HealthDashboard"
import MotionGraphicsSection from "../components/settings/MotionGraphicsSection"
import AIProviderSection from "../components/settings/AIProviderSection"
import ServiceKeysSection from "../components/settings/ServiceKeysSection"
import useSettings from "../hooks/useSettings"

function Section({ icon, title, description, children, accentColor }) {
  const theme = useTheme()
  const color = accentColor || theme.palette.primary.main
  return (
    <Card sx={{
      overflow: "visible",
      borderRadius: "20px",
      transition: "border-color 0.2s, box-shadow 0.2s",
      "&:hover": { borderColor: alpha(color, 0.4), boxShadow: `0 4px 20px ${alpha(color, 0.1)}` },
    }}>
      <CardContent sx={{ p: 0, "&:last-child": { pb: 0 } }}>
        {title && (
          <Box sx={{
            px: 3, pt: 2.5, pb: 2,
            background: `linear-gradient(135deg, ${alpha(color, 0.08)}, ${alpha(color, 0.02)})`,
            borderBottom: 1, borderColor: "divider",
          }}>
            <Stack direction="row" spacing={1.5} alignItems="center">
              {icon && (
                <Box sx={{
                  width: 36, height: 36, borderRadius: "12px",
                  bgcolor: alpha(color, 0.12),
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: color,
                }}>
                  {icon}
                </Box>
              )}
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 700, fontSize: "1rem", lineHeight: 1.3 }}>{title}</Typography>
                {description && (
                  <Typography variant="body2" sx={{ color: "text.secondary", fontSize: "0.8rem", mt: 0.25 }}>
                    {description}
                  </Typography>
                )}
              </Box>
            </Stack>
          </Box>
        )}
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      </CardContent>
    </Card>
  )
}


export default function Settings() {
  const { settings, loading, error, fetchSettings, updateSettings } = useSettings()

  if (loading) return (
    <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
      <Typography sx={{ color: "text.secondary" }}>Loading settings...</Typography>
    </Box>
  )
  if (error || !settings) return (
    <Box sx={{ p: 4, textAlign: "center" }}>
      <Typography sx={{ color: "error.main", mb: 2 }}>{error || "Failed to load settings"}</Typography>
      <Button variant="outlined" sx={{ borderRadius: "20px" }} onClick={fetchSettings}>Retry</Button>
    </Box>
  )

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* ── Header ── */}
      <Box sx={{
        px: 3, py: 2, flexShrink: 0,
        borderBottom: 1, borderColor: "divider",
        background: (t) => t.palette.mode === "dark"
          ? "linear-gradient(135deg, rgba(139,92,246,0.08) 0%, rgba(15,13,21,1) 100%)"
          : "linear-gradient(135deg, rgba(139,92,246,0.05) 0%, rgba(255,255,255,1) 100%)",
      }}>
        <Stack direction="row" spacing={1.5} alignItems="center">
          <IconSettings size={26} stroke={1.8} style={{ color: "var(--muted-foreground, #888)" }} />
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: -0.3 }}>
              Settings
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Manage your AI provider and system health
            </Typography>
          </Box>
        </Stack>
      </Box>

      {/* ── Scrollable content ── */}
      <Box sx={{ flex: 1, overflow: "auto", p: { xs: 2, md: 3 } }}>
      <Stack spacing={3} sx={{ maxWidth: 900, mx: "auto" }}>
        {/* AI Provider (BYOK) */}
        <Section
          icon={<IconRobot size={20} stroke={1.8} />}
          title="AI Provider"
          description="Bring your own Anthropic, OpenAI, or OpenRouter API key — encrypted and stored locally"
          accentColor="#8b5cf6"
        >
          <AIProviderSection settings={settings} updateSettings={updateSettings} />
        </Section>

        {/* Service API Keys (BYOK) */}
        <Section
          icon={<IconKey size={20} stroke={1.8} />}
          title="Service API Keys"
          description="Per-service API keys (YouTube, etc.) — encrypted locally, override .env at runtime"
          accentColor="#8b5cf6"
        >
          <ServiceKeysSection settings={settings} updateSettings={updateSettings} />
        </Section>

        {/* Optional add-ons */}
        <Section
          icon={<IconPuzzle size={20} stroke={1.8} />}
          title="Add-ons"
          description="Optional engines that install on demand into your data folder"
          accentColor="#a78bfa"
        >
          <MotionGraphicsSection />
        </Section>

        {/* System Health */}
        <Section
          icon={<IconActivity size={20} stroke={1.8} />}
          title="System Health"
          description="Service status, dependency checks, and storage usage"
          accentColor="#8b5cf6"
        >
          <HealthDashboard />
        </Section>
      </Stack>
      </Box>{/* end scrollable content */}
    </Box>
  )
}
