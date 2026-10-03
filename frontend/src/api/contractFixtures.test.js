import { describe, expect, test } from 'vitest'
import { normalizeGraphContract } from '../features/architecture/graphContract.js'

import jobFixture from '../../../docs/frontend-contract/analysis_job.json'
import diagFixture from '../../../docs/frontend-contract/diagnostics.json'
import navFixture from '../../../docs/frontend-contract/editor_navigate.json'
import graphSliceFixture from '../../../docs/frontend-contract/graph_slice.json'
import explFixture from '../../../docs/frontend-contract/node_explanation.json'
import projectsFixture from '../../../docs/frontend-contract/projects.json'

describe('Permanent Contract Fixture Validations', () => {
  test('projects.json has valid structure and authorized project entries', () => {
    expect(projectsFixture.api_version).toBe('v1')
    expect(Array.isArray(projectsFixture.projects)).toBe(true)
    expect(projectsFixture.projects.length).toBeGreaterThan(0)
    for (const proj of projectsFixture.projects) {
      expect(proj.id).toBeTypeOf('string')
      expect(proj.display_name).toBeTypeOf('string')
      expect(proj.available).toBeTypeOf('boolean')
    }
  })

  test('analysis_job.json matches JobResponse schema with valid JobState and canonical summary', () => {
    expect(jobFixture.api_version).toBe('v1')
    expect(jobFixture.analysis_id).toMatch(/^ana_/)
    expect(['completed', 'partially_completed', 'failed', 'cancelled', 'queued', 'running', 'scanning', 'parsing', 'resolving', 'building_graph', 'computing_metrics', 'submitted', 'validating']).toContain(jobFixture.state)
    expect(jobFixture.terminal).toBe(true)
    expect(jobFixture.progress).toBeDefined()
    expect(jobFixture.progress.percent).toBeTypeOf('number')

    // Canonical summary verification
    expect(jobFixture.result).toBeDefined()
    const summary = jobFixture.result.summary
    expect(summary).toBeDefined()
    expect(summary.source_units_total).toBeTypeOf('number')
    expect(summary.nodes_total).toBeTypeOf('number')
    expect(summary.edges_total).toBeTypeOf('number')
    expect(summary.nodes_by_kind).toBeTypeOf('object')
    expect(summary.edges_by_kind).toBeTypeOf('object')
    expect(summary.describes_full_result).toBe(true)

    // Ensure invented keys are absent
    expect(summary.total_files).toBeUndefined()
    expect(summary.total_nodes).toBeUndefined()
    expect(summary.total_edges).toBeUndefined()
  })

  test('diagnostics.json matches DiagnosticsResponse schema and normalizes through adapter', () => {
    expect(diagFixture.api_version).toBe('v1')
    expect(Array.isArray(diagFixture.items)).toBe(true)
    for (const item of diagFixture.items) {
      expect(item.code).toBeTypeOf('string')
      expect(['info', 'warning', 'error']).toContain(item.severity)
      expect(item.message).toBeTypeOf('string')
      expect(item.location).toBeDefined()
      expect(item.location.path).toBeTypeOf('string')
      expect(item.location.start_line).toBeGreaterThanOrEqual(1)
      expect(item.file_path).toBeUndefined()
      expect(item.line).toBeUndefined()
    }

    // Validate diagnostic item normalizes through frontend graph contract adapter
    const normalizedWithDiag = normalizeGraphContract({
      ...graphSliceFixture,
      diagnostics: diagFixture.items,
    })
    expect(normalizedWithDiag.diagnostics.length).toBe(diagFixture.items.length)
    const normDiag = normalizedWithDiag.diagnostics[0]
    expect(normDiag.code).toBe('FILE_SYNTAX_ERROR')
    expect(normDiag.severity).toBe('error')
    expect(normDiag.location).toBeDefined()
    expect(normDiag.location.path).toBe('pkg/module.py')
    expect(normDiag.location.startLine).toBe(1)
  })

  test('diagnostics with null location normalize cleanly without throwing or fabricating paths/lines', () => {
    // Real static locationless diagnostic matching parser_project output (e.g. whole-file encoding or policy exclusions)
    const locationlessDiag = {
      id: 'd_kgrlklldr23v7lr6rsxrhxxs4p',
      code: 'FILE_ENCODING_FAILURE',
      severity: 'error',
      phase: 'parsing',
      message: 'A Python file has an unsupported or invalid source encoding.',
      location: null,
      entity_id: null,
      edge_id: null,
      recoverable: false,
      consequence: 'skipped_or_partial',
      suggested_action: null,
      details: {},
    }

    const normalized = normalizeGraphContract({
      ...graphSliceFixture,
      diagnostics: [locationlessDiag],
    })

    expect(normalized.diagnostics.length).toBe(1)
    const normDiag = normalized.diagnostics[0]
    expect(normDiag.id).toBe('d_kgrlklldr23v7lr6rsxrhxxs4p')
    expect(normDiag.code).toBe('FILE_ENCODING_FAILURE')
    expect(normDiag.severity).toBe('error')
    expect(normDiag.phase).toBe('parsing')
    expect(normDiag.message).toBe('A Python file has an unsupported or invalid source encoding.')
    expect(normDiag.location).toBeNull()
    expect(normDiag.entityId).toBeNull()
    expect(normDiag.edgeId).toBeNull()
    expect(normDiag.consequence).toBe('skipped_or_partial')
  })

  test('editor_navigate.json contains valid navigate/pending/acknowledge cycles', () => {
    expect(navFixture.navigate_request.session_token).toMatch(/^cap_/)
    expect(navFixture.navigate_request.relative_path).toBeTypeOf('string')
    expect(navFixture.navigate_request.line).toBeGreaterThanOrEqual(1)

    expect(navFixture.navigate_response.status).toBe('queued')
    expect(navFixture.pending_navigate_response.has_command).toBe(true)
    expect(navFixture.acknowledge_request.status).toBe('delivered')
    expect(navFixture.acknowledge_response.acknowledged).toBe(true)
  })

  test('node_explanation.json has valid architectural breakdown', () => {
    expect(explFixture.api_version).toBe('v1')
    expect(explFixture.node_id).toBeTypeOf('string')
    expect(explFixture.role).toBeTypeOf('string')
    expect(explFixture.summary).toBeTypeOf('string')
    expect(Array.isArray(explFixture.recommendations)).toBe(true)
  })

  test('graph_slice.json normalizes cleanly through frontend graph contract adapter', () => {
    expect(graphSliceFixture.schema_version).toBe('1.0.0')
    expect(Array.isArray(graphSliceFixture.nodes)).toBe(true)
    expect(Array.isArray(graphSliceFixture.edges)).toBe(true)
    expect(Array.isArray(graphSliceFixture.evidence)).toBe(true)
    expect(graphSliceFixture.page).toBeDefined()
    expect(graphSliceFixture.page.returned_nodes).toBeTypeOf('number')

    const normalized = normalizeGraphContract(graphSliceFixture)
    expect(normalized).toBeDefined()
    expect(normalized.nodes.length).toBeGreaterThan(0)
    expect(normalized.edges.length).toBeGreaterThan(0)

    // Verify coordinates and evidence on normalized nodes/edges
    const nodeWithLoc = normalized.nodes.find((n) => n.location)
    expect(nodeWithLoc).toBeDefined()
    expect(nodeWithLoc.location.path).toBeTypeOf('string')
    expect(nodeWithLoc.location.startLine).toBeGreaterThanOrEqual(1)
  })
})
