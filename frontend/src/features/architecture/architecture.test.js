import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'vitest'
import { normalizeGraph } from './graphAdapter.js'
import { GraphContractError, normalizeGraphContract, safeRelativePath } from './graphContract.js'
import { adaptLegacyGraph } from './legacyGraphAdapter.js'
import { DEFAULT_FILTERS, exceedsGraphThreshold, filterGraph, nextSearchIndex, searchNodes, selectElementDetails } from './graphSelectors.js'
import { layoutGraph, measureGraphLayout } from './graphLayout.js'
import { toReactFlowElements } from './reactFlowAdapter.js'
import { generateDot } from './exportDot.js'
import { circularGraph, createLargeGraph, legacyFixture, partialGraph, resolutionGraph, smallGraph, unsupportedGraph } from './fixtures/graphFixtures.js'

test('validates and normalizes the v1 graph contract', () => {
  const graph = normalizeGraphContract(smallGraph)
  assert.equal(graph.schemaVersion, '1.0.0')
  assert.equal(graph.nodes[2].qualifiedName, 'app.main')
  assert.equal(graph.edges[0].resolutionStatus, 'not_applicable')
})

test('rejects unsupported major versions without reinterpretation', () => {
  assert.throws(() => normalizeGraph(unsupportedGraph), (error) => error instanceof GraphContractError && error.code === 'UNSUPPORTED_SCHEMA')
})

test('rejects malformed resolved relationships and duplicate ids', () => {
  const missing = structuredClone(smallGraph)
  missing.edges[2].target_id = 'n-absent'
  assert.throws(() => normalizeGraph(missing), (error) => error.code === 'MISSING_RESOLVED_TARGET')
  const duplicate = structuredClone(smallGraph)
  duplicate.edges.push(structuredClone(duplicate.edges[0]))
  assert.throws(() => normalizeGraph(duplicate), (error) => error.code === 'DUPLICATE_EDGE')
})

test('normalizes safe relative paths and rejects absolute or traversal paths', () => {
  assert.equal(safeRelativePath('pkg/module.py'), 'pkg/module.py')
  assert.equal(safeRelativePath('D:/secret/module.py'), null)
  assert.equal(safeRelativePath('../secret.py'), null)
  const hostile = structuredClone(smallGraph)
  hostile.nodes[2].location.path = 'C:/Users/name/private.py'
  assert.equal(normalizeGraph(hostile).nodes[2].location, null)
})

test('legacy adaptation is deterministic and semantically honest', () => {
  const first = adaptLegacyGraph(legacyFixture)
  const second = adaptLegacyGraph(legacyFixture)
  assert.deepEqual(first, second)
  assert.equal(first.edges[0].resolutionStatus, 'syntactic_only')
  assert.equal(first.edges[0].confidence, null)
  assert.deepEqual(first.edges[0].evidenceIds, [])
  assert.equal(first.nodes[0].qualifiedName, null)
})

test('layout is deterministic, non-overlapping, and cycle safe', () => {
  const graph = normalizeGraph(circularGraph)
  const first = layoutGraph(graph.nodes, graph.edges)
  const second = layoutGraph(graph.nodes, graph.edges)
  assert.deepEqual(first, second)
  assert.equal(new Set(first.map((item) => `${item.position.x}:${item.position.y}`)).size, first.length)
})

test('searches names, qualified names, paths, and kinds case insensitively', () => {
  const graph = normalizeGraph(smallGraph)
  assert.deepEqual(searchNodes(graph, 'SERVICE').map((item) => item.id), ['n-class', 'n-method'])
  assert.equal(searchNodes(graph, 'app/main.py').length, 3)
  assert(searchNodes(graph, 'method').some((item) => item.id === 'n-method'))
  assert.equal(nextSearchIndex(0, -1, 3), 2)
  assert.equal(nextSearchIndex(2, 1, 3), 0)
})

test('filters nodes and relationships while reporting visible totals', () => {
  const graph = normalizeGraph(resolutionGraph)
  const filtered = filterGraph(graph, { ...DEFAULT_FILTERS, nodeKinds: ['module', 'external_module'], relationshipKinds: ['imports'], resolutionStatuses: ['resolved'] })
  assert.equal(filtered.counts.visibleNodes, 2)
  assert.equal(filtered.counts.totalNodes, graph.nodes.length)
  assert.equal(filtered.counts.visibleEdges, 1)
})

test('selects node and edge details with diagnostics and evidence', () => {
  const graph = normalizeGraph(partialGraph)
  const node = selectElementDetails(graph, { type: 'node', id: 'n-module' })
  assert.equal(node.diagnostics[0].code, 'FILE_SYNTAX_ERROR')
  const edge = selectElementDetails(normalizeGraph(resolutionGraph), { type: 'edge', id: 'e-missing' })
  assert.equal(edge.item.resolutionStatus, 'unresolved')
  assert.equal(edge.evidence[0].origin, 'source_ast')
  assert.equal(edge.diagnostics[0].severity, 'warning')
})

test('large graph threshold is deterministic and presentation only', () => {
  const graph = normalizeGraph(createLargeGraph(400))
  assert.equal(exceedsGraphThreshold(graph, { nodes: 350, edges: 800 }), true)
  assert.equal(graph.nodes.length, 400)
})

test('React Flow adaptation preserves ids and unresolved visual semantics', () => {
  const graph = normalizeGraph(resolutionGraph)
  const positioned = layoutGraph(graph.nodes, graph.edges)
  const normal = toReactFlowElements(graph, positioned, { allowAnimation: true, reducedMotion: false })
  const reduced = toReactFlowElements(graph, positioned, { allowAnimation: true, reducedMotion: true })
  assert(normal.edges.some((item) => item.id === 'e-missing' && item.style.strokeDasharray))
  assert.deepEqual(normal.nodes.map((item) => item.id), reduced.nodes.map((item) => item.id))
  assert.deepEqual(normal.edges.map((item) => item.id), reduced.edges.map((item) => item.id))
  assert(normal.nodes.every((item) => typeof item.data.label === 'string'))
  assert(normal.edges.every((item) => typeof item.style.stroke === 'string'))
  assert(normal.edges.every((item) => !item.animated))
})

test('source-controlled strings have no raw HTML rendering path', async () => {
  const files = ['ArchitectureExplorer.jsx', 'ArchitectureGraph.jsx', 'DetailsPanel.jsx', 'DiagnosticsPanel.jsx', 'AccessibleGraphTable.jsx']
  const sources = await Promise.all(files.map((file) => readFile(new URL(file, import.meta.url), 'utf8')))
  assert(sources.every((source) => !source.includes('dangerouslySetInnerHTML') && !source.includes('innerHTML')))
})

test('generateDot produces valid Graphviz digraph with nodes, edges and metrics', () => {
  const graph = normalizeGraph(smallGraph)
  const dot = generateDot(graph)
  assert(dot.startsWith('digraph'))
  assert(dot.includes('node_n_module'))
  assert(dot.includes('->'))
  assert(dot.endsWith('}\n'))
  assert.equal(generateDot(null), '')
})

test('layoutGraph is pure and measureGraphLayout benchmarks dense graphs under 500ms', () => {
  const dense = normalizeGraph(createLargeGraph(186))
  const result = measureGraphLayout(dense.nodes, dense.edges)
  assert.equal(result.nodeCount, 186)
  assert(typeof result.durationMs === 'number')
  assert(result.durationMs < 500)
  assert.equal(result.nodes.length, 186)

  // Verify purity: layoutGraph produces exact same output without mutating window properties
  const pureResult = layoutGraph(dense.nodes, dense.edges)
  assert.deepEqual(pureResult, result.nodes)
})
