# Development setup

Use Python 3.10–3.14 and Node supported by Vite 8 (`^20.19.0` or `>=22.12.0`).

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm --prefix frontend ci
```

On macOS/Linux activate with `source .venv/bin/activate`. Never install project
tools globally. Configure aliases through [configuration](../configuration.md);
`.env` is ignored and is not loaded automatically.

```powershell
python -m uvicorn codestruct.api.app:app --app-dir backend/src --reload
npm --prefix frontend run dev
```

Run services in separate terminals. Vite proxies `/api`. SQLite is created in the
configured ignored runtime location and survives restart. Before cleanup stop all
processes, resolve the intended path, and remove only that runtime/test-output
directory—never the repository or a configured project. See [testing](testing.md)
and [operations](../operations.md).
