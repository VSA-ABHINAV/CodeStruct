from contextlib import asynccontextmanager
import io
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from backend.config import get_log_dir, get_resource_base, is_frozen, load_config

# Guard stdout/stderr in PyInstaller --noconsole mode on Windows (where they default to None)
if sys.stdout is None or sys.stderr is None:
    try:
        _log_file = get_log_dir() / "codestruct.log"
        _stream = open(_log_file, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = _stream
        if sys.stderr is None:
            sys.stderr = _stream
    except Exception:
        if sys.stdout is None:
            sys.stdout = io.StringIO()
        if sys.stderr is None:
            sys.stderr = io.StringIO()

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import webview

from backend.api import router as api_router
from backend.qwen_client import check_ollama_connection

BASE_DIR = get_resource_base()
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup validation for CodeStruct services and persisted configuration."""
    cfg = load_config()
    models_dir = cfg.get("ollama_models_dir")
    if models_dir:
        os.environ["OLLAMA_MODELS"] = str(models_dir)

    ollama_host = cfg.get("ollama_host", "http://localhost:11434").rstrip("/")
    app.state.ollama_connected = check_ollama_connection(tags_url=f"{ollama_host}/api/tags", timeout=1.0)
    if app.state.ollama_connected:
        print(f"[CodeStruct Startup] Ollama service connected ({cfg.get('ollama_model', 'qwen2.5-coder:3b')}).")
    else:
        print("[CodeStruct Startup] Ollama service not reachable. Qwen panel will show Disconnected.")
    yield


app = FastAPI(title="CodeStruct", lifespan=lifespan)

# Initialize app state variables
app.state.last_graph = None
app.state.ollama_connected = False
app.state.webview_window = None

# Include API routes
app.include_router(api_router)

# Mount frontend/static directory
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_root():
    """Serve the desktop shell index.html."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


def find_available_port(host: str = "127.0.0.1", default_port: int = 8000, max_attempts: int = 20) -> int:
    """Find an available port starting from default_port."""
    for p in range(default_port, default_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                continue
    return default_port


def start(
    host: str = "127.0.0.1",
    port: int = 8000,
    func=None,
    func_args=None,
    project_path: Optional[str] = None,
):
    """Start Uvicorn in a background thread and launch the pywebview single window."""
    app.state.initial_project_path = project_path

    # Check and select available port starting from requested port
    actual_port = find_available_port(host, port)
    if actual_port != port:
        print(f"[CodeStruct] Port {port} is busy; automatically using port {actual_port}.")
    port = actual_port

    uvicorn_kwargs = {
        "app": app,
        "host": host,
        "port": port,
        "log_level": "info",
        "access_log": False,
    }
    if is_frozen():
        # Avoid Uvicorn default logging formatter TTY check failing under --noconsole
        uvicorn_kwargs["log_config"] = None

    config = uvicorn.Config(**uvicorn_kwargs)
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait until Uvicorn server is running and listening
    timeout = 10.0
    start_time = time.time()
    while not server.started and (time.time() - start_time < timeout):
        time.sleep(0.05)

    if not server.started:
        raise RuntimeError("Uvicorn server failed to start within timeout.")

    # Create single native window
    query_str = f"?project={quote(project_path)}" if project_path else ""
    window = webview.create_window(
        title="CodeStruct",
        url=f"http://{host}:{port}/{query_str}",
        width=1280,
        height=800,
        min_size=(800, 600),
    )
    app.state.webview_window = window

    def on_closed():
        server.should_exit = True

    window.events.closed += on_closed

    try:
        if func is not None:
            target_args = func_args if func_args is not None else window
            webview.start(func, target_args)
        else:
            webview.start()
    finally:
        app.state.webview_window = None
        server.should_exit = True
        server_thread.join(timeout=3.0)


# Alias main for convenience
main = start

if __name__ == "__main__":
    start()
