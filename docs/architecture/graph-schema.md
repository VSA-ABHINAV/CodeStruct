# CodeStruct graph schema

## Purpose and authority

This document defines the canonical MVP analysis and graph contract. It is a
target design, not current output. The characterized legacy shape remains in
[current-data-contract.md](current-data-contract.md) and is migrated as described
in [migration-plan.md](migration-plan.md).

The canonical model is edge-centric: nodes own entity facts; edges own
relationships and their evidence. API projections may attach inbound/outbound
summaries to nodes, but those are derived and never another source of truth.

## Identity rules

| Identity | Format and stability |
| --- | --- |
| `analysis_id` | Opaque UUIDv7 string created for every submitted attempt, including a cache-hit attempt; never reused |
| `result_id` | `res_` plus base32 SHA-256 of project fingerprint, analyzer version, parser/runtime version, effective policy fingerprint, and graph schema major/minor; shared only by byte-equivalent reusable results |
| `graph_id` | `grf_` plus base32 SHA-256 of `result_id` and graph projection version; stable for an immutable full result |
| `node_id` | `n_` plus base32 SHA-256 of node kind and canonical semantic key |
| `edge_id` | `e_` plus base32 SHA-256 of kind, source ID, target/reference key, resolution status, and semantic discriminator |
| `evidence_id` | `v_` plus base32 SHA-256 of origin, source-unit ID, normalized span, observation kind, and normalized observed text hash |
| `diagnostic_id` | `d_` plus base32 SHA-256 of stable code, phase, safe source-unit ID/span, and occurrence discriminator |

Hashes are encoded lowercase without padding and use explicit field separators.
The unhashed semantic key is retained for debugging only when safe. Project paths
are normalized to project-relative POSIX form, Unicode-normalized, and compared
under the platform policy. Absolute project paths and source contents never enter
public IDs. Collision detection is mandatory: unequal semantic keys producing an
existing ID fail the result with `IDENTITY_COLLISION` rather than merging data.

File semantic keys are normalized relative paths. Module keys are import-qualified
module names plus package context. Symbol keys are `(module_id, lexical qualified
name, kind, definition span)`, preserving repeated/nested definitions. IDs remain
stable for unchanged semantic inputs but are not promised across schema-major
identity changes.

## Canonical enums

### Node kinds

`project`, `directory`, `file`, `package`, `module`, `class`, `function`,
`async_function`, `method`, `async_method`, `external_module`, and
`unresolved_symbol`.

Files and modules are distinct: a file is a source artifact; a module is an
import namespace. Package `__init__.py` can back both a file and package/module
node. Directories are presentation/containment entities and do not imply Python
packages.

### Relationship kinds

`contains`, `defines`, `imports`, `inherits`, `calls`, `constructs`, and
`references`. MVP UI groups `imports` as dependency relationships. `references`
is emitted only where its supported static semantics are documented; it is not a
catch-all for uncertain calls.

### Resolution status

- `not_applicable`: containment or a direct observation needs no target lookup.
- `resolved`: exactly one supported static target was selected.
- `ambiguous`: multiple supported candidates remain.
- `unresolved`: lookup was attempted but no supported target was selected.
- `syntactic_only`: the expression was observed but MVP resolution does not claim
  a target.

### Evidence origin

- `source_ast`: direct syntax observed by the Python AST parser.
- `static_resolution`: a deterministic resolver derivation linked to source AST
  evidence.
- `runtime_trace`: reserved; prohibited in MVP output.
- `type_inference`: reserved; prohibited in MVP output.
- `llm_inference`: reserved; prohibited in MVP output.

Origins are append-only within a schema major. A future provider adds evidence;
it cannot mutate, replace, or increase the confidence of a `source_ast` record.

### Confidence

`exact`, `high`, `medium`, `low`, and `unknown`. Confidence always includes a
stable `reason_code`. Direct AST facts are normally `exact`; resolution confidence
depends on documented rules. `unknown` is required when no defensible ranking
exists. Consumers must use `resolution_status`, not confidence, to decide whether
an edge is resolved.

## Canonical records

Types use JSON notation: `?` means nullable, and `[]` means an ordered array.

### `SourceLocation`

| Field | Type | Meaning |
| --- | --- | --- |
| `source_unit_id` | string | ID of included file/source unit |
| `path` | string | safe project-relative POSIX path |
| `start_line`, `start_column` | integer | one-based line and column |
| `end_line`, `end_column` | integer? | one-based exclusive end when supplied by parser |

Ranges must be positive, ordered, and inside the parsed unit. An absent end is
explicitly `null`, not guessed. Parser adapters normalize zero-based parser byte
offsets into this one-based Unicode-column contract and test multibyte source.

### `EvidenceRecord`

| Field | Type | Meaning |
| --- | --- | --- |
| `evidence_id` | string | stable evidence identity |
| `origin` | enum | provenance category above |
| `observation_kind` | string | stable machine name such as `import_statement` or `call_expression` |
| `location` | `SourceLocation?` | exact safe source location, if available |
| `observed_text_hash` | string? | hash of normalized bounded syntax, never source content itself |
| `excerpt` | string? | optional bounded redacted excerpt; disabled by default |
| `explanation` | string | safe human explanation |

### `GraphNode`

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | stable node ID |
| `kind` | enum | node kind |
| `name` | string | short display name |
| `qualified_name` | string | project/module/lexical qualified name |
| `parent_id` | string? | canonical containment parent |
| `module_id`, `file_id` | string? | owning module/file where applicable |
| `location` | `SourceLocation?` | definition location |
| `modifiers` | string[] | sorted supported modifiers such as `async` |
| `attributes` | object | versioned, bounded scalar/array extension properties |

Unknown attributes are ignored by tolerant readers. Core semantic fields cannot
move into `attributes` within schema major 1.

### `GraphEdge`

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | stable semantic relationship ID |
| `kind` | enum | relationship kind |
| `source_id` | string | existing source node ID |
| `target_id` | string? | existing target node when resolved/represented |
| `target_reference` | string? | normalized unresolved or ambiguous reference |
| `resolution_status` | enum | semantics above |
| `confidence` | enum | evidence strength, separate from status |
| `confidence_reason` | string | stable reason code |
| `evidence_ids` | string[] | sorted, nonempty evidence references except derived containment |
| `occurrence_count` | integer | number of retained observations represented by this edge |
| `attributes` | object | versioned bounded extension properties |

A resolved edge requires `target_id`; unresolved or ambiguous edges require a
safe `target_reference`. Repeated semantic relationships aggregate into one edge
and retain every distinct evidence record and the occurrence count. Circular
relationships are ordinary edges plus summary metrics; missing targets remain
unresolved rather than disappearing.

### `Diagnostic`

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | stable diagnostic ID |
| `code` | string | documented stable machine code |
| `severity` | `info` / `warning` / `error` | user impact |
| `phase` | job phase | producing phase |
| `message` | string | redacted safe summary |
| `location` | `SourceLocation?` | permitted project-relative location |
| `entity_id`, `edge_id` | string? | related graph record |
| `recoverable` | boolean | whether retry/scope correction can help |
| `consequence` | string | skipped/partial/failed effect |
| `suggested_action` | string? | safe user action |
| `details` | object | bounded non-secret structured context |

Stack traces, absolute paths, environment values, and source contents are never
public diagnostic details.

### `AnalysisMetadata`

| Field | Type | Meaning |
| --- | --- | --- |
| `analysis_id`, `result_id`, `graph_id` | string | attempt/result/graph identities |
| `schema_version` | string | graph contract SemVer, initially `1.0.0` |
| `api_version` | string | producing API, initially `v1` |
| `analyzer_version` | string | installed analyzer SemVer |
| `python_runtime` | string | exact parser runtime |
| `source_language` | string | `python` |
| `source_grammar` | string | configured grammar version |
| `policy_fingerprint` | string | non-secret effective-policy digest |
| `project_fingerprint` | string | privacy-preserving project-content digest |
| `started_at`, `finished_at` | RFC 3339 timestamp? | lifecycle times |
| `duration_ms` | integer? | monotonic measured duration |
| `cache` | object | hit, created time, age, stale reason, refresh flag |
| `partial` | boolean | true iff useful result has incomplete scope |
| `partial_reasons` | string[] | stable reason codes |
| `exclusions` | object | counts by safe reason; never secret names |
| `limits` | object | configured caps and reached cap, if any |

### `SummaryCounts`

Contains total and returned counts for source units, nodes by kind, edges by kind,
resolution status, confidence, diagnostics by severity/code, excluded entries,
and failed/skipped files. Counts use non-negative integers and state whether they
describe the full result or current slice.

### `AnalysisGraph`

```json
{
  "schema_version": "1.0.0",
  "metadata": {},
  "summary": {},
  "nodes": [],
  "edges": [],
  "evidence": [],
  "diagnostics_summary": {},
  "page": {
    "limit": 250,
    "next_cursor": null,
    "has_more": false,
    "slice": {"mode": "full_page", "root_ids": [], "depth": null}
  }
}
```

`partial=true` is independent of pagination: a complete result may be paged; a
partial result may have no next page. Detailed diagnostics are retrieved through
their endpoint, while the graph embeds only a summary and IDs relevant to
returned records.

## Graph slices and pagination

- Default graph queries return a cursor page in stable `(kind, qualified_name,
  id)` / `(kind, source_id, target_id-or-reference, id)` order.
- Cursors are opaque, signed with a process-local application key, scoped to
  `graph_id` and query filters, expire with result retention, and reveal no path.
- `limit` has a low default and policy maximum. Invalid, expired, or cross-query
  cursors return a typed error.
- `root_id` plus bounded `depth` returns a neighborhood slice; `package_id` or
  safe relative directory scope returns an aggregation/expansion slice.
- Filters include node kind, edge kind, resolution status, confidence, and query
  text. Responses state full-result totals and returned/visible totals.
- No API request can bypass server complexity, response-byte, or query-time caps.
  Clients progressively expand from summaries rather than requesting all records.

## Determinism

Traversal paths, AST observations, symbol candidates, IDs, record arrays,
attribute keys, diagnostics, evidence, and summaries are canonically ordered.
Serialization uses UTF-8, sorted object keys for semantic fingerprints, exact
bounded source-byte hashes for cache invalidation, finite numeric values, and explicit nulls. Timestamps,
durations, cache age, and `analysis_id` are excluded from semantic result equality.

## Compatibility rules

- `schema_version` follows SemVer independently from API and analyzer versions.
- Patch versions clarify validation or add no fields. Minor versions may add
  optional fields, enum values, diagnostic codes, or relationship kinds; readers
  must ignore unknown optional fields and render unknown enums generically.
- Removing/renaming fields, changing identity or meaning, making optional data
  required, or changing types requires a schema major and API compatibility plan.
- Every stored result records its exact schema. Read-time migration may upgrade a
  supported old schema transactionally; it never silently reinterprets evidence.
- NetworkX node/edge attributes, React Flow coordinates, layout state, cache row
  IDs, absolute paths, AST nodes, and Python object representations are forbidden
  from the canonical/public schema.

## Evidence-class separation

| Class | MVP treatment |
| --- | --- |
| Directly observed syntax | Emit `source_ast` evidence and syntactic entities/references; it says what text structure exists, not what executes |
| Statically resolved relationship | Emit separate `static_resolution` derivation referencing source evidence, target, rule, status, and confidence |
| Unresolved reference | Retain safe reference, evidence, attempted rule, and `unresolved`/`ambiguous`/`syntactic_only`; never drop it |
| Runtime-observed relationship | Reserved `runtime_trace`; no MVP producer and never synthesized from AST |
| Type-inferred relationship | Reserved `type_inference`; no MVP producer |
| LLM-inferred relationship | Reserved `llm_inference`; no MVP producer and cannot alter deterministic static records |

## Validation invariants

All referenced node/evidence/diagnostic IDs exist in the same immutable result;
IDs and arrays are unique; resolved endpoints exist; spans are valid; public paths
are relative; terminal partial metadata agrees with job status; reserved evidence
origins are absent in MVP; and serialization validates before repository commit
and again at the API boundary.
