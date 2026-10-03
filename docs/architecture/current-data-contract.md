# CodeStruct current data contract

## Contract status

This document describes the JSON currently returned by the FastAPI application
and consumed by the React application. It is descriptive, not a promise that the
shape is sufficient for future analysis.

**Verified:** `GET /` and `GET /analyze` are the only application routes. Both
use HTTP GET, accept no route, query, or request-body parameters, and declare no
FastAPI `response_model`. The structures below are ordinary Python dictionaries
and lists serialized by FastAPI.

**Interpretation:** the implementation has an implicit wire contract enforced by
the frontend and characterization tests, but not by Pydantic validation, static
types, versioning, or a shared schema.

## Endpoints

### `GET /`

Successful response:

```json
{
  "message": "CodeStruct Backend is Working!"
}
```

| Field | Current type | Meaning | Limitation |
| --- | --- | --- | --- |
| `message` | string | Fixed health-style message | Does not verify sample-path access or perform an analyzer health check |

### `GET /analyze`

Successful top-level shape:

```text
AnalysisResponse
  files: FileAnalysis[]
  dependencies: Dependency[]
```

| Field | Current type | Meaning | Limitation |
| --- | --- | --- | --- |
| `files` | array of file-analysis objects | Syntactic observations for top-level `.py` files in the selected directory | Order comes from `os.listdir`; files that cannot be processed fail the request rather than appearing with diagnostics |
| `dependencies` | array of dependency objects | Same-directory import edges inferred from the recorded import strings | Contains import-file matches only; it is not a call, inheritance, package, or resolved symbol graph |

No response field identifies contract version, analyzed root, timestamp, tool
version, Python version, warnings, errors, skipped files, duration, or completeness.

## File-analysis object

Every item currently returned in `files` has these six fields:

| Field | Current type | Actual meaning | Accuracy boundary |
| --- | --- | --- | --- |
| `file` | string | `os.path.basename(file_path)` | Basename only; not a relative path, module name, stable ID, or unique repository identity |
| `imports` | array of strings | Distinct `ast.Import` names and non-empty `ast.ImportFrom.module` values observed anywhere in the file | Does not retain imported symbols, aliases, relative level, scope, location, or internal/external classification |
| `classes` | array of strings | Distinct `ast.ClassDef.name` values observed anywhere in the file | No qualified name, owner scope, bases beyond the separate limited list, decorator, signature, path, or source position |
| `functions` | array of strings | Distinct `ast.FunctionDef.name` values observed anywhere in the file | Includes methods and nested functions without distinction; excludes `AsyncFunctionDef`; overloads and equal short names collapse |
| `inheritance` | array of inheritance objects | Distinct child/parent short-name pairs extracted from supported class base expressions | Syntactic only; no class resolution, module qualification, generic arguments, evidence, or unresolved result |
| `calls` | array of call objects | Distinct supported call-expression shapes observed anywhere in the file | Syntactic only; no caller, callee resolution, count, order after deduplication, source position, or runtime evidence |

Collection order is the first-observed order from `ast.walk`, after duplicate
removal. That ordering is implementation behavior and is not documented by an
explicit API guarantee.

### Inheritance object

```text
Inheritance
  child: string
  parent: string
```

| Field | Current type | Actual meaning | Limitation |
| --- | --- | --- | --- |
| `child` | string | The current `ClassDef.name` | Short name only |
| `parent` | string | `Name.id` for `class Child(Base)` or final `Attribute.attr` for `class Child(pkg.Base)` | `pkg.Base` becomes `Base`; other AST base shapes are omitted; no proof that the parent exists |

The sample class `Admin(User)` produces:

```json
{
  "child": "Admin",
  "parent": "User"
}
```

### Call object variants

The `calls` array currently contains two object shapes.

Simple-name call:

```text
FunctionCallObservation
  type: "function"
  name: string
```

| Field | Current type | Actual meaning | Limitation |
| --- | --- | --- | --- |
| `type` | literal string `"function"` | `Call.func` was an `ast.Name` | Does not prove the target is a function; a bare constructor has the same shape |
| `name` | string | The observed `Name.id` | Alias, scope, definition, receiver, and qualified target are unknown |

Single-attribute call:

```text
MethodCallObservation
  type: "method"
  object: string
  function: string
```

| Field | Current type | Actual meaning | Limitation |
| --- | --- | --- | --- |
| `type` | literal string `"method"` | `Call.func` was an `ast.Attribute` whose immediate value was an `ast.Name` | Does not prove method dispatch; module-qualified constructors also receive this label |
| `object` | string | Immediate receiver syntax from `Call.func.value.id` | No variable, import, instance, or type resolution |
| `function` | string | Final attribute text from `Call.func.attr` | No qualified callee or definition link |

For example, `user.UserService()` is returned as:

```json
{
  "type": "method",
  "object": "user",
  "function": "UserService"
}
```

This is a syntactic attribute-call observation, not a resolved method call. Calls
whose receiver is another attribute or call expression are absent.

## Dependency object

Every item currently returned in `dependencies` has three fields:

```text
Dependency
  source: string
  target: string
  type: "import"
```

| Field | Current type | Actual meaning | Limitation |
| --- | --- | --- | --- |
| `source` | string | Basename of the file containing the import observation | Not a unique module or file ID |
| `target` | string | `<first import segment>.py` when that path exists beside the source | Package modules and nested paths are reduced incorrectly; basename collisions are possible |
| `type` | literal string `"import"` | Edge came from the import matching rule | No subtype for `import` versus `from`, and no confidence or evidence |

The builder computes a candidate with
`imported_module.split(".")[0] + ".py"` and retains it only when
`os.path.exists(os.path.join(project_path, candidate))` succeeds. Consequently:

- `import user` produces an edge to `user.py` when that sibling exists.
- `from user import User` also records module `user` and can produce the same
  edge, but the imported `User` symbol is not retained.
- `import package.module` checks for sibling `package.py`, not
  `package/module.py`.
- Standard-library, third-party, missing, and package imports generally have no
  dependency entry unless a same-named sibling file happens to exist.
- Circular imports may produce edges in both directions, but no cycle field or
  diagnostic is returned.
- Equal edge dictionaries are collapsed, so multiple import statements or sites
  do not produce multiple edges.

## Verified sample response

With the backend process working directory set to `backend`, the literal
`../sample_project` path currently produces this data:

```json
{
  "files": [
    {
      "file": "database.py",
      "imports": [],
      "classes": ["Database"],
      "functions": ["get_user"],
      "inheritance": [],
      "calls": []
    },
    {
      "file": "main.py",
      "imports": ["user"],
      "classes": [],
      "functions": [],
      "inheritance": [],
      "calls": [
        {"type": "method", "object": "user", "function": "UserService"},
        {"type": "method", "object": "service", "function": "get_user"}
      ]
    },
    {
      "file": "user.py",
      "imports": ["database"],
      "classes": ["UserService", "User", "Admin"],
      "functions": ["get_user"],
      "inheritance": [{"child": "Admin", "parent": "User"}],
      "calls": [
        {"type": "method", "object": "database", "function": "Database"},
        {"type": "method", "object": "db", "function": "get_user"}
      ]
    }
  ],
  "dependencies": [
    {"source": "main.py", "target": "user.py", "type": "import"},
    {"source": "user.py", "target": "database.py", "type": "import"}
  ]
}
```

The observed file order above is not guaranteed because the implementation does
not sort `os.listdir` results. Characterization tests compare file content by
name and dependency content as sets where order is not semantically required.

## Failure and HTTP behavior

The code defines no application error object. Missing directories, permission
errors, UTF-8 decoding errors, syntax errors, and file races raise Python
exceptions. Through FastAPI, an unhandled error normally becomes an HTTP 500
response, but the exact server error body is framework behavior rather than a
CodeStruct contract. No successful partial response is defined.

The frontend assumes a successful JSON object containing both arrays. It does not
check HTTP status, validate the fields, or provide a compatibility fallback.
Therefore, even additive backend work needs care when it changes identifiers,
ordering, nullability, call variants, or collection shape.

## Syntactic observations versus resolved relationships

| Current output | Classification |
| --- | --- |
| File basenames | Filesystem-derived labels |
| Import strings | AST syntax observations |
| Class and function names | AST syntax observations |
| Inheritance pairs | Partially normalized AST syntax observations |
| Function and method call objects | Partially normalized AST syntax observations |
| Dependency edges | Same-directory filename matches derived from import syntax |

None of these fields establishes a fully qualified symbol, semantic caller-to-
callee link, runtime execution, source evidence location, or architectural
component.

## Assumptions, limitations, and deferred decisions

- **Assumption:** the backend runs with `backend` as its process working directory.
- **Assumption:** input files are trusted, readable UTF-8 Python files.
- **Known limitation:** file and edge identity is basename-based.
- **Known limitation:** no version or schema validation protects the consumer.
- **Known limitation:** pytest-based HTTP contract tests remain pending until the
  Phase 2 development dependencies are installed and run.
- **Deferred:** future identifiers, path representation, package semantics,
  diagnostics, evidence fields, call variants, API versioning, pagination, and
  migration compatibility.

See [current-architecture.md](current-architecture.md) for component boundaries,
execution flow, frontend coupling, and prioritized technical debt.
