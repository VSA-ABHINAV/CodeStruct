# CodeStruct architecture decision records

These Phase 5 ADRs are accepted target decisions but are not implemented behavior.
They are interpreted with [target architecture](../architecture/target-architecture.md),
[graph schema](../architecture/graph-schema.md), [API contract](../architecture/api-contract.md),
[security model](../architecture/security-model.md), and
[migration plan](../architecture/migration-plan.md).

| ADR | Decision |
| --- | --- |
| [ADR-001](adr-001-parser-strategy.md) | Standard-library Python AST parser |
| [ADR-002](adr-002-graph-domain-and-networkx.md) | Dataclass graph domain with a NetworkX adapter |
| [ADR-003](adr-003-visualization-library.md) | Retain React Flow behind a renderer adapter |
| [ADR-004](adr-004-background-jobs.md) | Async coordination with bounded spawned worker processes |
| [ADR-005](adr-005-cache-and-persistence.md) | Per-user SQLite job and result repository |
| [ADR-006](adr-006-api-versioning.md) | `/api/v1` with temporary legacy compatibility |
| [ADR-007](adr-007-python-packaging.md) | Setuptools `src` layout and bundled release frontend |
| [ADR-008](adr-008-api-framework-and-serialization.md) | FastAPI, Pydantic DTOs, and standard JSON |
| [ADR-009](adr-009-frontend-state-and-layout.md) | React reducer state and worker-based layered layout |
| [ADR-010](adr-010-configuration-observability-and-testing.md) | TOML configuration, stdlib structured logs, and layered tests |
