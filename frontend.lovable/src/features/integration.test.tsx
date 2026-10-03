import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { demoGraph, demoDiagnostics } from './fixtures';
import { liveTransport, mergePages, normalizeGraph, demoTransport } from './transport';
import { useWorkbench } from './useWorkbench';
import { buildFlow } from './workbench';
import type { AnalysisJob, Transport } from './types';

const completed: AnalysisJob = { analysis_id: 'ana_real_42', state: 'completed', terminal: true, partial: false, cache_hit: false, progress: { phase: 'completed', percent: 100, message_code: 'done' }, diagnostics_summary: { info: 0, warning: 0, error: 0 } };
const project = { id: 'actual_project', display_name: 'Actual project', description: null, available: true };
const mock = (): Transport => ({ ...demoTransport, mode: 'live', listProjects: vi.fn().mockResolvedValue([project]), analyze: vi.fn().mockResolvedValue(completed), status: vi.fn().mockResolvedValue(completed), getGraph: vi.fn().mockResolvedValue(demoGraph), getDiagnostics: vi.fn().mockResolvedValue([]) });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, '', '/'); });

describe('backend integration', () => {
  it('uses metadata graph ID and preserves canonical nullable data', () => {
    const graph = normalizeGraph({ ...demoGraph, graph_id: '', metadata: { graph_id: 'graph_actual' }, diagnostics: [{ ...demoDiagnostics[0], location: null }] });
    expect(graph.graph_id).toBe('graph_actual');
    expect(graph.diagnostics[0].location).toBeNull();
  });
  it('sends editor credential and one-based coordinates, surfaces backend errors', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ status: 'queued' }), { status: 200 }));
    await liveTransport.navigate('main.py', 4, 5, 'cap_test_only');
    expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string)).toEqual({ session_token: 'cap_test_only', relative_path: 'main.py', line: 4, column: 5 });
    fetcher.mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'OPTION_UNSUPPORTED', message: 'Unsupported option' } }), { status: 400 }));
    await expect(liveTransport.analyze('actual_project')).rejects.toThrow('Unsupported option');
    await expect(liveTransport.navigate('main.py', 4)).rejects.toThrow('Launch an analysis from Thonny');
  });
  it('requests bounded pages and deduplicates only matching results', async () => {
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ...demoGraph, metadata: { graph_id: 'real_graph' } }), { status: 200 }));
    const page = await liveTransport.getGraph('ana_real_42', 'cursor opaque');
    expect(fetcher.mock.calls[0][0]).toContain('limit=200&cursor=cursor+opaque');
    expect(mergePages(page, page).nodes.length).toBe(page.nodes.length);
    expect(() => mergePages(page, { ...page, graph_id: 'other' })).toThrow('different results');
  });
  it('polls a real ID before retrieving graph and uses available project IDs', async () => {
    const transport = mock();
    transport.analyze = vi.fn().mockResolvedValue({ ...completed, terminal: false, state: 'queued' });
    const { result } = renderHook(() => useWorkbench(transport));
    await waitFor(() => expect(result.current.projectId).toBe('actual_project'));
    expect(transport.analyze).not.toHaveBeenCalled();
    await act(() => result.current.load(false));
    expect(transport.status).toHaveBeenCalledWith('ana_real_42', expect.any(AbortSignal));
    expect(transport.getGraph).toHaveBeenCalledWith('ana_real_42', null, expect.any(AbortSignal));
    expect(result.current.graph).not.toBeNull();
  });
  it('replays captured IDE startup under StrictMode and clears session on project change', async () => {
    window.history.replaceState({}, '', '/?analysis_id=ana_real_42&session_token=cap_test_only&keep=yes');
    const transport = mock();
    const { result } = renderHook(() => useWorkbench(transport), { wrapper: StrictMode });
    await waitFor(() => expect(result.current.graph).not.toBeNull());
    expect(window.location.search).toBe('?keep=yes');
    expect(result.current.session).toBe('cap_test_only');
    expect(transport.analyze).not.toHaveBeenCalled();
    act(() => result.current.chooseProject('other'));
    expect(result.current.session).toBeNull();
    expect(result.current.graph).toBeNull();
  });
  it('discards a late result when the project changes', async () => {
    const transport = mock(); let resolve!: (job: AnalysisJob) => void;
    transport.analyze = () => new Promise(r => { resolve = r; });
    const { result } = renderHook(() => useWorkbench(transport));
    await waitFor(() => expect(result.current.projectId).toBe('actual_project'));
    let task!: Promise<void>;
    act(() => { task = result.current.load(false); });
    act(() => result.current.chooseProject('other'));
    await act(async () => { resolve(completed); await task; });
    expect(transport.getGraph).not.toHaveBeenCalled();
    expect(result.current.graph).toBeNull();
  });
  it('positions real IDs separately and keeps unresolved edges out of fabricated connections', () => {
    const graph = { ...demoGraph, nodes: demoGraph.nodes.map((n, i) => ({ ...n, id: `real_${i}`, kind: 'async_method' })), edges: [] };
    const flow = buildFlow(graph, null, () => {});
    expect(new Set(flow.nodes.map(n => `${n.position.x},${n.position.y}`)).size).toBe(graph.nodes.length);
    expect(flow.edges).toEqual([]);
  });
});
