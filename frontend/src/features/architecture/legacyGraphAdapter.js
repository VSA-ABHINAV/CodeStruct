import { safeRelativePath } from './graphContract.js'

const stableHash = (value) => {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(36)
}

const legacyId = (kind, ...parts) => `legacy-${kind}-${stableHash(parts.join('\u001f'))}`
const array = (value) => Array.isArray(value) ? value : []

// Transitional Phase 8 boundary. It deliberately exposes absent v1 evidence as
// unavailable and must be removed only after the Phase 9 compatibility window.
export function adaptLegacyGraph(payload) {
  const files = array(payload?.files)
  const dependencies = array(payload?.dependencies)
  const nodes = []
  const fileIds = new Map()

  files.forEach((file, fileIndex) => {
    const suppliedPath = typeof file?.file === 'string' ? file.file : null
    const path = safeRelativePath(suppliedPath) || `unavailable-file-${fileIndex + 1}`
    const fileId = legacyId('file', path)
    fileIds.set(path, fileId)
    nodes.push({
      id: fileId, kind: 'file', displayName: path, qualifiedName: null, parentId: null,
      moduleId: null, fileId, location: suppliedPath === path ? { sourceUnitId: null, path, startLine: null, startColumn: null, endLine: null, endColumn: null } : null,
      modifiers: [], classification: 'internal',
      attributes: {
        legacy: true,
        classes: array(file.classes).join(', '),
        functions: array(file.functions).join(', '),
        imports: array(file.imports).join(', '),
        inheritance: array(file.inheritance).map((item) => `${item?.child ?? '?'} → ${item?.parent ?? '?'}`).join(', '),
        calls: array(file.calls).map((item) => item?.type === 'method' ? `${item?.object ?? '?'}.${item?.function ?? '?'}()` : `${item?.name ?? '?'}()`).join(', '),
      },
    })
  })

  const edges = dependencies.map((dependency, index) => {
    const source = typeof dependency?.source === 'string' ? dependency.source : `unknown-source-${index}`
    const target = typeof dependency?.target === 'string' ? dependency.target : `unknown-target-${index}`
    return {
      id: legacyId('edge', source, target, dependency?.type ?? 'dependency', String(index)),
      kind: 'imports', sourceId: fileIds.get(source) || legacyId('missing-source', source),
      targetId: fileIds.get(target) || null, targetReference: fileIds.has(target) ? null : target,
      resolutionStatus: 'syntactic_only', confidence: null, confidenceReason: null,
      candidateIds: [], evidenceIds: [], diagnosticIds: [], occurrenceCount: 1,
      attributes: { legacy: true, import_kind: 'module' },
      targetClassification: fileIds.has(target) ? 'internal' : 'unresolved',
    }
  })

  return {
    source: 'legacy', schemaVersion: null,
    metadata: { partial: false, compatibility: 'legacy-v0', evidenceAvailable: false },
    summary: {}, nodes, edges, evidence: [], diagnostics: [],
  }
}
