import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { analysisApi, mergeGraphSlices } from '../../api/analysisApi.js'
import { AnalysisPoller } from '../../api/analysisPoller.js'
import { AnalysisApiError, safeApiMessage, toAnalysisError } from '../../api/analysisErrors.js'

const initial = {
  job: null,
  graph: null,
  error: null,
  submitting: false,
  cancelling: false,
  graphLoading: false,
  pageLoading: false,
  provenance: null,
}

export function useAnalysisJob(api = analysisApi) {
  const [view, setView] = useState(initial)
  const poller = useMemo(() => new AnalysisPoller(api), [api])
  const submission = useRef(false)
  const pageRequest = useRef(false)

  useEffect(() => () => poller.stop(), [poller])

  const update = useCallback((change) => {
    setView((current) => ({
      ...current,
      ...change,
      submitting: false,
      cancelling: false,
    }))
  }, [])

  const submit = useCallback(async (project, options = {}) => {
    if (submission.current) return
    if (!project?.root_id || !project?.relative_path?.trim()) {
      setView((current) => ({ ...current, error: toAnalysisError(new Error()), submitting: false }))
      return
    }
    submission.current = true
    poller.stop()
    const prov = { root_id: project.root_id, relative_path: project.relative_path.trim() }
    setView({ ...initial, submitting: true, provenance: prov })
    try {
      const { job } = await api.submit(project, options)
      poller.start(job, (change) => update({ ...change, provenance: prov }))
    } catch (error) {
      setView({ ...initial, error: toAnalysisError(error), provenance: prov })
    } finally {
      submission.current = false
    }
  }, [api, poller, update])

  const load = useCallback((analysisId) => {
    submission.current = false
    poller.stop()
    if (typeof analysisId !== 'string' || !analysisId.trim() || analysisId.length > 128 || !/^[A-Za-z0-9_.~-]+$/.test(analysisId.trim())) {
      setView({
        ...initial,
        error: new AnalysisApiError('MALFORMED_ID', safeApiMessage('MALFORMED_ID'), 400, false),
      })
      return
    }
    const id = analysisId.trim()
    setView({ ...initial, graphLoading: true, provenance: null })
    poller.startById(id, (change) => update({ ...change, provenance: null }))
  }, [poller, update])


  const setError = useCallback((error) => {
    poller.stop()
    setView({ ...initial, error: toAnalysisError(error), provenance: null })
  }, [poller])

  const cancel = useCallback(async () => {
    if (!view.job || view.cancelling) return
    setView((current) => ({ ...current, cancelling: true }))
    try {
      const job = await api.cancel(view.job.analysis_id)
      update({ job })
    } catch (error) {
      update({ error: toAnalysisError(error) })
    }
  }, [api, update, view.cancelling, view.job])

  const loadMore = useCallback(async () => {
    const cursor = view.graph?.page?.next_cursor
    const analysisId = view.job?.analysis_id
    if (!cursor || !analysisId || pageRequest.current) return
    pageRequest.current = true
    setView((current) => ({ ...current, pageLoading: true, error: null }))
    try {
      const page = await api.graph(analysisId, { limit: 1000, cursor })
      setView((current) => current.job?.analysis_id === analysisId
        ? { ...current, graph: mergeGraphSlices([current.graph, page]), pageLoading: false }
        : current)
    } catch (error) {
      setView((current) => current.job?.analysis_id === analysisId
        ? { ...current, pageLoading: false, error: toAnalysisError(error) }
        : current)
    } finally {
      pageRequest.current = false
    }
  }, [api, view.graph, view.job])

  return {
    ...view,
    submit,
    load,
    setError,
    cancel,
    loadMore,
    hasMore: Boolean(view.graph?.page?.next_cursor),
  }
}

