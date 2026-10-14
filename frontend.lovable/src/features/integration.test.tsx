import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { demoGraph, demoDiagnostics, graphToDot } from './fixtures';
import { liveTransport, mergePages, normalizeGraph, demoTransport } from './transport';
import { useWorkbench } from './useWorkbench';
import { buildFlow, getNodeLevel } from './workbench';
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

  it('assigns top-down hierarchy levels correctly (0=project, 1=file, 2=module, 3=class, 4=function, 5=method)', () => {
    const projectNode = { ...demoGraph.nodes[0], id: 'n_proj', kind: 'project', parent_id: null };
    const fileNode = { ...demoGraph.nodes[0], id: 'n_file', kind: 'file', parent_id: 'n_proj' };
    const moduleNode = { ...demoGraph.nodes[0], id: 'n_mod', kind: 'module', parent_id: 'n_file' };
    const classNode = { ...demoGraph.nodes[0], id: 'n_cls', kind: 'class', parent_id: 'n_mod' };
    const funcNode = { ...demoGraph.nodes[0], id: 'n_fn', kind: 'function', parent_id: 'n_mod' };
    const methodNode = { ...demoGraph.nodes[0], id: 'n_mth', kind: 'method', parent_id: 'n_cls' };
    const funcInClass = { ...demoGraph.nodes[0], id: 'n_fn_cls', kind: 'function', parent_id: 'n_cls' };
    const all = [projectNode, fileNode, moduleNode, classNode, funcNode, methodNode, funcInClass];

    expect(getNodeLevel(projectNode, all)).toBe(0);
    expect(getNodeLevel(fileNode, all)).toBe(1);
    expect(getNodeLevel(moduleNode, all)).toBe(2);
    expect(getNodeLevel(classNode, all)).toBe(3);
    expect(getNodeLevel(funcNode, all)).toBe(4);
    expect(getNodeLevel(methodNode, all)).toBe(5);
    expect(getNodeLevel(funcInClass, all)).toBe(5);

    const flow = buildFlow({ ...demoGraph, nodes: all, edges: [] }, null, () => {});
    const nodeY = new Map(flow.nodes.map(n => [n.id, n.position.y]));
    expect(nodeY.get('n_proj')).toBeLessThan(nodeY.get('n_file')!);
    expect(nodeY.get('n_file')).toBeLessThan(nodeY.get('n_mod')!);
    expect(nodeY.get('n_mod')).toBeLessThan(nodeY.get('n_cls')!);
    expect(nodeY.get('n_cls')).toBeLessThan(nodeY.get('n_fn')!);
    expect(nodeY.get('n_fn')).toBeLessThan(nodeY.get('n_mth')!);
  });

  it('satisfies R3 by distinguishing loaded slice export from complete graph export and handling partial load', async () => {
    // Partial load state with 1 node loaded out of 10
    const partialGraph = {
      ...demoGraph,
      partial_load: true,
      summary: { ...demoGraph.summary, nodes_total: 10 },
      nodes: [demoGraph.nodes[0]],
      edges: [],
    };
    // Slice export serializes exactly the loaded slice
    const sliceDot = graphToDot(partialGraph);
    expect(sliceDot).toContain(`"${demoGraph.nodes[0].id}"`);
    expect(sliceDot).not.toContain(`"${demoGraph.nodes[1].id}"`);
    expect(partialGraph.partial_load).toBe(true);

    // Complete export calls the backend API endpoint
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(new Blob(['digraph full {}']), { status: 200 }));
    const completeBlob = await liveTransport.exportDot('ana_real_42');
    expect(fetcher).toHaveBeenCalledWith('/api/v1/analyses/ana_real_42/export/dot', expect.anything());
    expect(completeBlob).toBeInstanceOf(Blob);
  });

  it('triggers native folder selection and retrieves whole-project symbol tree', async () => {
    const transport = mock();
    transport.chooseFolder = vi.fn().mockResolvedValue({
      cancelled: false,
      root_id: 'root_selected',
      project_name: 'selected_project',
      path: 'C:\\Users\\test\\project',
      analysis_id: 'ana_real_42',
    });
    transport.getTree = vi.fn().mockResolvedValue({
      api_version: 'v1',
      request_id: 'req_1',
      analysis_id: 'ana_real_42',
      root_id: 'root_selected',
      root_path: 'C:\\Users\\test\\project',
      tree: {
        id: 'dir_root',
        name: 'project',
        path: '',
        kind: 'directory',
        children: [],
      },
      excluded: [{ path: '.git', reason: 'Version control directory excluded by policy' }],
    });

    const { result } = renderHook(() => useWorkbench(transport));
    await act(async () => {
      await result.current.openFolder();
    });

    expect(transport.chooseFolder).toHaveBeenCalled();
    expect(result.current.projectId).toBe('root_selected');
    await waitFor(() => expect(result.current.tree).not.toBeNull());
    expect(result.current.tree?.excluded.length).toBe(1);
    expect(result.current.tree?.excluded[0].path).toBe('.git');
  });
});
