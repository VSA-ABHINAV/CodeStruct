from contextlib import asynccontextmanager
import logging
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import webview

from backend.api import router as api_router
from backend.qwen_client import check_ollama_connection

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup validation for CodeStruct services (Phase 9)."""
    app.state.ollama_connected = check_ollama_connection(timeout=1.0)
    if app.state.ollama_connected:
        print("[CodeStruct Startup] Ollama service connected (qwen2.5-coder:3b).")
    else:
        print("[CodeStruct Startup] Ollama service not reachable. Qwen panel will show Disconnected.")
    yield


app = FastAPI(title="CodeStruct", lifespan=lifespan)

# Initialize app state variables
app.state.last_graph = None
app.state.ollama_connected = False

# Include API routes
app.include_router(api_router)

# Mount frontend/static directory
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def read_root():
    """Serve the minimal placeholder index.html."""
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

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait until Uvicorn server is running and listening
    timeout = 5.0
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
        server.should_exit = True
        server_thread.join(timeout=3.0)


# Alias main for convenience
main = start

if __name__ == "__main__":
    start()
