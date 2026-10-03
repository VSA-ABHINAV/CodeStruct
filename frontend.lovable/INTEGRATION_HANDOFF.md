# Connected CodeStruct frontend

This exported Lovable design now runs as a local Vite/React SPA against the existing FastAPI backend. The original `frontend/` is preserved. Export-only TanStack server/routes and unused components remain in this folder as reference; `index.html` -> `src/main.tsx` -> `features/workbench.tsx` is the active application.

## Run locally

From this directory:

```powershell
npm.cmd ci
npm.cmd run dev
```

Start the existing backend using the project's normal backend/Thonny launcher. Development requests under `/api/v1` proxy to `http://127.0.0.1:8000`. Override with `CODESTRUCT_BACKEND_URL` when testing a different loopback port. Live mode is the default; `.env.example` documents explicit demo mode. A failed live API request never substitutes demo data.

The prototype launcher's `frontendDirectory` points here after integration. Stop/restart task-owned prototype services to activate it; already running frontend processes retain their old directory.

## Validation

```powershell
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

Build with `CODESTRUCT_FRONTEND_BASE=/app/` for backend-mounted assets. Release tooling selects this directory. The backend keeps its existing `/api/v1` contracts, filesystem authorization, selected-file capabilities and plugin acknowledgment protocol.

From the repository root, `.venv\Scripts\python.exe tools\bundle_lovable_frontend.py` copies that verified build into the backend's local `/app` directory, retaining existing assets and backing up the previous entry point under `.codestruct/lovable-integration-backup`. Then open `http://127.0.0.1:8000/app/` when the normal backend is running.

## Connected behavior

- Authorized-project discovery; supported static create/refresh requests.
- Sequential status polling, cancellation, cache/partial/failure states and diagnostics.
- Actual analysis IDs for graph retrieval, explanations and DOT downloads.
- Explicit bounded graph pages, matching-result validation and deduplicated Load more.
- Canonical metadata graph identity, source locations, dictionary attributes and evidence.
- StrictMode-safe IDE URL capture/scrubbing, in-memory credentials and session clearing.
- Credential-bearing editor navigation; queued request feedback does not claim cursor delivery.
- Deterministic non-overlapping node positions, dynamic source list, synchronized graph/table, theme and fullscreen.

Unsupported analysis options/runtime/RAG features are not implemented by this UI. The existing pending real Thonny cursor gate remains separate; frontend integration must not mark it complete. Advanced layout, full accessibility evaluation and later backend milestones are not implied by this handoff.
