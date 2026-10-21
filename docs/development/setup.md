# Development setup

Use Python 3.10–3.14 and Node supported by Vite 8 (`^20.19.0` or `>=22.12.0`).

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
npm --prefix frontend.lovable ci
```

On macOS/Linux activate with `source .venv/bin/activate`. Never install project
tools globally. Configure aliases through [configuration](../configuration.md);
`.env` is ignored and is not loaded automatically.

### Running Development Services

```powershell
python -m uvicorn codestruct.api.app:app --app-dir backend/src --reload
npm --prefix frontend.lovable run dev
```

### Integrated Thonny Single-Window Workflow

To run the complete integrated application inside the Thonny IDE:

```powershell
.\prototype-launcher\Start-CodeStruct-Prototype.ps1
```

Or execute `Start-CodeStruct-Prototype.cmd` from the repository root. This starts the backend and frontend development servers on loopback and launches Thonny. Inside Thonny, open any Python folder in the **File view** and select **Tools → CodeStruct** to open the embedded workbench tab. Run `.\prototype-launcher\Stop-CodeStruct-Prototype.ps1` to stop background services safely without closing Thonny.

Run services in separate terminals. Vite proxies `/api`. SQLite is created in the
configured ignored runtime location and survives restart. Before cleanup stop all
processes, resolve the intended path, and remove only that runtime/test-output
directory—never the repository or a configured project. See [testing](testing.md)
and [operations](../operations.md).
