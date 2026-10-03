import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, mergePages } from './transport';
import type { AnalysisJob, Diagnostic, GraphResult, Project, Transport } from './types';

export function captureHandoff() {
  const query = new URLSearchParams(window.location.search);
  return { analysisId: query.get('analysis_id'), token: query.get('session_token') };
}
const message = (error: unknown) => error instanceof Error ? error.message : 'The request failed.';
const delay = (ms: number, signal: AbortSignal) => new Promise<void>((resolve, reject) => {
  const stop = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')); };
  const timer = setTimeout(() => { signal.removeEventListener('abort', stop); resolve(); }, ms);
  signal.addEventListener('abort', stop, { once: true });
  if (signal.aborted) stop();
});

export function useWorkbench(transport: Transport) {
  const [handoff] = useState(captureHandoff);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProject] = useState('');
  const [graph, setGraph] = useState<GraphResult | null>(null);
  const [diagnostics, setDiagnostics] = useState<Diagnostic[]>([]);
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [status, setStatus] = useState('Connecting to backend');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [paging, setPaging] = useState(false);
  const [session, setSession] = useState(handoff.token);
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const activeId = useRef<string | null>(null);

  const run = useCallback(async (refresh: boolean, initialId?: string) => {
    const version = ++generation.current;
    controller.current?.abort();
    const abort = new AbortController(); controller.current = abort;
    setBusy(true); setError(null); setGraph(null); setDiagnostics([]); setJob(null); setPaging(false); activeId.current = null;
    if (!initialId) setSession(null);
    const current = () => !abort.signal.aborted && generation.current === version;
    try {
      let next = initialId ? await transport.status(initialId, abort.signal) : await transport.analyze(projectId, refresh, abort.signal);
      if (!current()) return;
      activeId.current = next.analysis_id;
      while (current()) {
        setJob(next); setStatus(`${next.progress.phase}${next.progress.percent == null ? '' : ` (${next.progress.percent}%)`}`);
        if (next.terminal) break;
        await delay(650, abort.signal);
        try { next = await transport.status(next.analysis_id, abort.signal); }
        catch (err) {
          if (err instanceof ApiError && err.retryAfter) { await delay(err.retryAfter * 1000, abort.signal); continue; }
          throw err;
        }
      }
      if (!current()) return;
      if (!['completed', 'partially_completed', 'cache_hit'].includes(next.state)) {
        setStatus(next.state);
        if (next.state === 'failed') setError('Analysis failed. Check diagnostics and retry.');
        const items = await transport.getDiagnostics(next.analysis_id, abort.signal);
        if (current()) setDiagnostics(items);
        return;
      }
      const result = await transport.getGraph(next.analysis_id, null, abort.signal);
      const items = await transport.getDiagnostics(next.analysis_id, abort.signal);
      if (!current()) return;
      setGraph(result); setDiagnostics(items);
      setStatus(next.partial ? 'Partially completed' : next.cache_hit ? 'Cached result' : 'Analysis complete');
    } catch (err) { if (current()) { setError(message(err)); setStatus('Request failed'); } }
    finally { if (current()) setBusy(false); }
  }, [projectId, transport]);

  // Capture once before scrubbing; each StrictMode replay loads the captured ID.
  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete('session_token'); url.searchParams.delete('analysis_id');
    window.history.replaceState({}, '', url.pathname + url.search + url.hash);
    let disposed = false;
    void transport.listProjects().then(items => {
      if (disposed) return;
      setProjects(items); setProject(items.find(p => p.available)?.id ?? '');
      if (!handoff.analysisId) setStatus(items.some(p => p.available) ? 'Select a project and Analyze' : 'No authorized projects available');
    }).catch(err => { if (!disposed) setError(message(err)); });
    if (handoff.analysisId) void run(false, handoff.analysisId);
    return () => { disposed = true; ++generation.current; controller.current?.abort(); };
    // run depends on selected project, but initial IDE launch must occur only on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transport, handoff]);

  const chooseProject = (id: string) => {
    ++generation.current; controller.current?.abort(); activeId.current = null;
    setProject(id); setSession(null); setGraph(null); setDiagnostics([]); setJob(null); setBusy(false); setPaging(false); setError(null); setStatus('Ready to analyze');
  };
  const loadMore = async () => {
    if (!graph?.page?.next_cursor || !activeId.current || paging) return;
    const version = generation.current; const id = activeId.current;
    setPaging(true); setError(null);
    try {
      const next = await transport.getGraph(id, graph.page.next_cursor, controller.current?.signal);
      if (generation.current === version) setGraph(previous => previous ? mergePages(previous, next) : next);
    } catch (err) { if (generation.current === version) setError(message(err)); }
    finally { if (generation.current === version) setPaging(false); }
  };
  const cancel = async () => {
    if (!activeId.current) return;
    const version = generation.current;
    try { const result = await transport.cancel(activeId.current); if (generation.current === version) { setJob(result); setStatus(result.state); } }
    catch (err) { if (generation.current === version) setError(message(err)); }
  };
  return { projects, projectId, chooseProject, graph, diagnostics, job, status, setStatus, error, setError, busy, paging, session, analysisId: activeId.current, load: run, loadMore, cancel };
}
