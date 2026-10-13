// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (c) 2025-2026 ViralMint Contributors
/**
 * Trends — trending videos found by the trend analyzer, on their own page.
 *
 * A trend result is a LEAD, not a file you own. It has no
 * bytes on disk, nothing to play, nothing to edit — and it grows fast enough to
 * dwarf the library it was filed inside.
 *
 * Library means "files I have" and this page means "things I could
 * make".
 */
import { useCallback, useEffect, useState } from "react"
import { Box, Stack, Button, Tooltip, Skeleton } from "@mui/material"
import { IconTrendingUp, IconRefresh, IconCompass } from "@tabler/icons-react"
import { useNavigate } from "react-router-dom"
import http from "../api/http"
import PageHero from "../components/PageHero"
import TrendsTab from "../components/videos/TrendsTab"
import useDocumentTitle from "../hooks/useDocumentTitle"
import useAppStore from "../store/appStore"

const DEFAULT_ROWS = 50

export default function Trends() {
  useDocumentTitle("Trends")
  const navigate = useNavigate()
  const showSnackbar = useAppStore((s) => s.showSnackbar)
  const jobs = useAppStore((s) => s.jobs)   // polled once, app-wide, in Layout

  const [results, setResults] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(DEFAULT_ROWS)
  const [loading, setLoading] = useState(true)

  const fetchResults = useCallback(async (jobId = null, offset = 0, limit = DEFAULT_ROWS) => {
    try {
      const params = new URLSearchParams({ limit, offset })
      if (jobId) params.set("job_id", jobId)
      const { data } = await http.get(`/api/trends/results?${params}`)
      setResults(data.results || [])
      setTotal(data.total || 0)
    } catch {
      showSnackbar("Could not load trends", "error")
    } finally {
      setLoading(false)
    }
  }, [showSnackbar])

  useEffect(() => { fetchResults(null, 0, DEFAULT_ROWS) }, [fetchResults])

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <PageHero
        icon={<IconTrendingUp size={22} stroke={1.8} />}
        title="Trends"
        subtitle="Trending videos worth borrowing from — leads, not files"
        accentColor="#8b5cf6"
        actions={
          <Stack direction="row" spacing={1}>
            <Tooltip title="Refresh results">
              <Button size="small" variant="outlined" sx={{ minWidth: 0, px: 1, borderRadius: "20px" }}
                aria-label="Refresh results"
                onClick={() => { setPage(0); fetchResults(null, 0, rowsPerPage) }}>
                <IconRefresh size={16} stroke={1.8} />
              </Button>
            </Tooltip>
            <Button size="small" variant="contained"
              startIcon={<IconCompass size={16} stroke={1.8} />}
              sx={{ borderRadius: "20px", px: 2, textTransform: "none", fontWeight: 600 }}
              onClick={() => navigate("/")}>
              Explore trends
            </Button>
          </Stack>
        }
      />
      <Box sx={{ flex: 1, overflow: "auto", p: { xs: 2, md: 3 } }}>
        {loading ? (
          <Stack spacing={1}>
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} variant="rounded" height={72} />
            ))}
          </Stack>
        ) : (
          <TrendsTab
            jobs={jobs}
            results={results}
            total={total}
            page={page}
            rowsPerPage={rowsPerPage}
            onFetchResults={(jobId, offset, limit) => {
              if (offset === 0) setPage(0)
              fetchResults(jobId, offset, limit)
            }}
            onPageChange={(_, p, jobId) => { setPage(p); fetchResults(jobId || null, p * rowsPerPage, rowsPerPage) }}
            onRowsPerPageChange={(e, jobId) => {
              const rpp = parseInt(e.target.value, 10)
              setRowsPerPage(rpp); setPage(0); fetchResults(jobId || null, 0, rpp)
            }}
          />
        )}
      </Box>
    </Box>
  )
}
