import { toAnalysisError } from './analysisErrors.js'
import { retrieveGraph } from './analysisApi.js'
const RESULT_STATES = new Set(['completed', 'partially_completed'])

export class AnalysisPoller {
  constructor(api, { intervalMs = 750, maxNetworkRetries = 3, schedule = (callback, delay) => setTimeout(callback, delay), cancelSchedule = (timer) => clearTimeout(timer) } = {}) {
    this.api = api
    this.intervalMs = Math.max(250, intervalMs)
    this.maxNetworkRetries = maxNetworkRetries
    this.schedule = schedule
    this.cancelSchedule = cancelSchedule
    this.generation = 0
    this.timer = null
    this.inFlight = false
    this.retries = 0
  }

  stop() {
    this.generation += 1
    if (this.timer !== null) this.cancelSchedule(this.timer)
    this.timer = null
    this.inFlight = false
  }

  _poll(analysisId, notify, initialJob = null) {
    this.stop()
    const generation = this.generation
    this.retries = 0
    if (initialJob) {
      notify({ job: initialJob, error: null })
      if (RESULT_STATES.has(initialJob.state)) {
        notify({ job: initialJob, graphLoading: true, error: null })
        Promise.all([retrieveGraph(this.api, initialJob.analysis_id), this.api.diagnostics(initialJob.analysis_id)])
          .then(([graph, diagnostics]) => {
            if (generation === this.generation) {
              notify({ job: initialJob, graph: { ...graph, diagnostics: diagnostics.items ?? graph.diagnostics ?? [] }, graphLoading: false, error: null })
            }
          })
          .catch((error) => {
            if (generation === this.generation) {
              notify({ graphLoading: false, error: toAnalysisError(error) })
            }
          })
        return
      }
      if (initialJob.terminal) return
    }

    const tick = async () => {
      if (generation !== this.generation || this.inFlight) return
      this.inFlight = true
      try {
        const current = await this.api.status(analysisId)
        if (generation !== this.generation) return
        notify({ job: current, error: null })
        this.retries = 0
        if (RESULT_STATES.has(current.state)) {
          notify({ job: current, graphLoading: true, error: null })
          const [graph, diagnostics] = await Promise.all([
            retrieveGraph(this.api, current.analysis_id),
            this.api.diagnostics(current.analysis_id),
          ])
          if (generation === this.generation) {
            notify({ job: current, graph: { ...graph, diagnostics: diagnostics.items ?? graph.diagnostics ?? [] }, graphLoading: false, error: null })
          }
          return
        }
        if (current.terminal) return
      } catch (error) {
        if (generation !== this.generation) return
        const err = toAnalysisError(error)
        if (!err.recoverable || this.retries >= this.maxNetworkRetries) {
          notify({ graphLoading: false, error: err })
          return
        }
        this.retries += 1
      } finally {
        this.inFlight = false
      }
      if (generation === this.generation) {
        this.timer = this.schedule(tick, this.intervalMs * Math.max(1, this.retries))
      }
    }

    this.timer = this.schedule(tick, initialJob ? this.intervalMs : 0)
  }

  start(job, notify) {
    this._poll(job.analysis_id, notify, job)
  }

  startById(analysisId, notify) {
    this._poll(analysisId, notify, null)
  }
}

