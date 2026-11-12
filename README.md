# CodeStruct

> **A Native Desktop Static Analysis Platform & Architectural Intelligence Environment for Python**

CodeStruct is an offline-first desktop application that statically parses Python codebases into interactive architecture graphs, sortable symbol tables, design-pattern catalogs, change-impact blast radiuses, and AI-synthesized architectural component clusters.

Analysis is **100% static** — powered exclusively by Python's standard library `ast` module. **No code from analyzed projects is ever executed, evaluated, or imported**, ensuring total safety when inspecting untrusted or arbitrary repositories.

---

## Table of Contents

- [Architectural Overview](#architectural-overview)
- [Prerequisite System Capabilities](#prerequisite-system-capabilities)
- [Mandatory System Notice: Local AI Runtime & Model](#mandatory-system-notice-local-ai-runtime--model)
- [Step-by-Step Environment Setup](#step-by-step-environment-setup)
- [Local AI Installation & Model Configuration](#local-ai-installation--model-configuration)
- [Execution Guide](#execution-guide)
- [Verification & Test Suite](#verification--test-suite)
- [Core Feature Tour](#core-feature-tour)
- [REST API Reference](#rest-api-reference)
- [Directory Structure & Functional Roles](#directory-structure--functional-roles)
- [Troubleshooting & Common Pitfalls](#troubleshooting--common-pitfalls)

---

## Architectural Overview

CodeStruct operates as a single unified desktop process combining a local FastAPI ASGI service running on loopback (`127.0.0.1`) and a native `pywebview` window. All fonts, styles, and graph libraries are vendored locally for complete offline operability.

```mermaid
flowchart TD
    subgraph UI ["Desktop Native Shell (pywebview / Edge WebView2 / WebKit / WebKitGTK)"]
        HTML["index.html (Semantic Desktop Shell)"]
        CSS["app.css (Blueprint Dark Design System)"]
        JS["app.js (UI Controller & Selection Sync)"]
        CY["Cytoscape.js 3.28.1 (Vendored Offline Graph Engine)"]
    end

    subgraph Backend ["FastAPI Application (Uvicorn Loopback Daemon)"]
        API["api.py (REST Route Endpoints)"]
        PORT["Dynamic Port Resolver (Port 8000-8020)"]
    end

    subgraph Core ["Static Analysis Core (ast engine - zero runtime code execution)"]
        ANALYZER["analyzer.py (AST Parser & Edge Resolver)"]
        CACHE["cache.py (SHA-256 Incremental AST Cache)"]
        PATTERNS["patterns.py (Singleton, Factory, Observer Detectors)"]
        IMPACT["compute_impact (Reverse BFS Dependency Blast Radius)"]
        ARCH["advanced_architecture.py (Component Clustering & Validation Safety Net)"]
    end

    subgraph LLM ["Local AI Runtime (Optional Ollama Daemon)"]
        OLLAMA["Ollama Service (http://localhost:11434)"]
        MODEL["qwen2.5-coder:3b (Local Neural Weights)"]
    end

    UI <-->|HTTP JSON / REST| Backend
    Backend --> Core
    Core <-->|Context-Grounded JSON| LLM
```

### Architectural Guarantees
1. **Zero Execution of Analyzed Code:** Parsing uses Python's built-in `ast` module. Code is parsed into syntactic trees without invoking `exec`, `eval`, or dynamic `import`.
2. **Offline-First:** Fonts (Inter, JetBrains Mono) and Cytoscape.js are fully vendored in `codestruct/frontend/static/vendor/`. No runtime internet connection is required.
3. **Deterministic Symbol Accounting:** The Phase 19 validation layer guarantees that every real symbol in the AST graph is accounted for in component clusters or in `unclustered_symbol_ids`. Any hallucinated IDs from the local LLM are dropped and logged.
4. **Resilient Port Binding:** Automatically detects if port `8000` is occupied (e.g., `[Errno 10048]`) and binds to the next available loopback port (`8001`–`8020`).

---

## Prerequisite System Capabilities

Before initializing CodeStruct, ensure your host machine satisfies these baseline hardware and OS toolchain requirements:

| Component | Minimum Specification | Recommended Specification |
|---|---|---|
| **Operating System** | Windows 10/11 (64-bit), macOS 12+ (Intel/Apple Silicon), Linux (Ubuntu 20.04+, Debian 11+, Fedora 36+, Arch) | Windows 11, macOS 14+ (M-series), or modern Linux |
| **Python Toolchain** | Python `3.10` – `3.14` with `pip` and `venv` | Python `3.12` or `3.14` (Verified on `3.14.6`) |
| **Git** | Git `>= 2.30` | Git `>= 2.40` |
| **System Memory (RAM)** | **4 GB** (Core static analysis, graph, patterns, table view) | **8 GB – 16 GB** (Required for concurrent local LLM inference) |
| **Disk Storage** | **500 MB** (Repository, virtual environment, AST caches) | **+3.0 GB** (Ollama runtime + `qwen2.5-coder:3b` model weights) |
| **Desktop GUI Runtime** | Windows: Edge WebView2<br>macOS: Cocoa WebKit<br>Linux: WebKit2GTK 4.0/4.1 | Preinstalled on Windows 10/11 & macOS |

### OS-Specific System Dependencies (Install Before Python Setup)

- **Windows (10/11):**
  - Microsoft Edge WebView2 Runtime is built into Windows 10 (1803+) and Windows 11. On Windows Server / LTSC, install the [WebView2 Evergreen Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).
  - Ensure [Python 3.10+](https://www.python.org/downloads/windows/) (with **"Add python.exe to PATH"** checked) and [Git for Windows](https://git-scm.com/download/win) are installed.

- **macOS (12+):**
  - Native Cocoa WebKit is built in; no extra GUI runtime is needed.
  - Install Xcode Command Line Tools and Python 3 if not already present:
    ```zsh
    xcode-select --install
    brew install python@3.12 git
    ```

- **Linux (Ubuntu / Debian / Fedora / Arch):**
  - On minimal Linux distributions, both Python's `venv` module and `pywebview`'s GTK/WebKit2GTK bindings must be installed via your system package manager:
    ```bash
    # Ubuntu 24.04+ / Debian 12+ (Bookworm/Trixie)
    sudo apt-get update && sudo apt-get install -y git python3 python3-venv python3-pip python3-gi gir1.2-webkit2-4.1 libgirepository1.0-dev

    # Ubuntu 20.04 / 22.04 / Debian 11 (uses webkit2-4.0)
    sudo apt-get update && sudo apt-get install -y git python3 python3-venv python3-pip python3-gi gir1.2-webkit2-4.0 libgirepository1.0-dev

    # Fedora / RHEL
    sudo dnf install -y git python3 python3-pip python3-gobject webkit2gtk4.1

    # Arch Linux
    sudo pacman -S --needed git python python-pip python-gobject webkit2gtk-4.1
    ```

---

## Mandatory System Notice: Local AI Runtime & Model

> [!WARNING]
> ### CRITICAL NOTICE: LOCAL OPEN-SOURCE AI MODEL DOWNLOAD & SYSTEM RESOURCE IMPACT
>
> CodeStruct includes an optional local AI chat assistant and an Advanced Architecture clustering synthesizer powered by an open-source Large Language Model (LLM).
>
> By following the Ollama installation steps below, you are about to **download and execute an open-source neural network model directly on your local CPU/GPU**.
>
> **Explicit Implications for Local System Resources & Storage:**
> 1. **Disk Storage:** Pulling `qwen2.5-coder:3b` requires approximately **2.0 GB** of network bandwidth and allocates **~2.2 GB** of permanent disk space inside Ollama's local model store (`~/.ollama/models` on macOS/Linux or `%USERPROFILE%\.ollama\models` on Windows).
> 2. **Memory (RAM / VRAM) Footprint:** When loaded for inference, the model allocates between **3.0 GB and 4.5 GB** of system RAM (or dedicated GPU VRAM if CUDA, ROCm, or Apple Metal acceleration is available).
> 3. **Processor & Thermal Load:** Inference drives sustained multi-core CPU or GPU utilization, increasing thermal output, fan noise, and battery drain on portable devices.
>
> **Graceful Degradation Guarantee:**
> If your hardware lacks ~2.2 GB free disk space or 8+ GB total RAM, **skip the Ollama installation**. CodeStruct operates **100% reliably in degraded mode**: AST static parsing, interactive relationship graphs, symbol tables, Martin's Instability metrics, change-impact blast radius analysis, and design-pattern detection all work completely offline with zero loss of core capability. The Assistant dock will simply show an unobtrusive `Disconnected` badge.

---

## Step-by-Step Environment Setup

Execute the exact commands for your operating system and shell to deploy CodeStruct cleanly from a fresh clone.

### 1. Clone the Repository

Run the following in your terminal:

```bash
git clone https://github.com/VSA-ABHINAV/CodeStruct.git
cd CodeStruct
```

*(Note: If Phase 19/20 features are not yet merged into `master`, switch to the active feature branch: `git checkout feature/phase-19-20-tooling`)*

### 2. Create & Activate an Isolated Virtual Environment

- **Windows (PowerShell):**
  ```powershell
  python -m venv venv

  # Allow venv activation script in the current PowerShell session if restricted:
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

  .\venv\Scripts\Activate.ps1
  ```

- **Windows (Command Prompt / CMD):**
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```

- **macOS / Linux (Bash or Zsh):**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

*(Once activated, your shell prompt displays `(venv)`, and both `python` and `pip` point directly to your isolated environment across all operating systems.)*

### 3. Install Python Dependencies

With `(venv)` active, upgrade `pip` and install the requirements file:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Verify Package Integrity

Confirm zero dependency conflicts:

```bash
python -m pip check
```
*(Expected output: `No broken requirements found.`)*

---

## Local AI Installation & Model Configuration

*(Optional — skip this section if running without local AI features.)*

> [!CAUTION]
> **Resource Check Before Executing:** Confirm you have at least **2.5 GB free disk space** and **4.5 GB available RAM/VRAM** before pulling `qwen2.5-coder:3b`. See the [Mandatory System Notice](#mandatory-system-notice-local-ai-runtime--model) above.

### Step 1: Install Ollama Runtime

- **Windows (PowerShell or CMD via `winget`):**
  ```powershell
  winget install Ollama.Ollama
  ```
  *(Alternatively, download the GUI installer from [https://ollama.com/download/windows](https://ollama.com/download/windows). Restart your terminal after installation so `ollama` is on your `PATH`.)*

- **macOS (Bash/Zsh via Homebrew):**
  ```zsh
  brew install ollama
  ```
  *(Alternatively, download the macOS app from [https://ollama.com/download/mac](https://ollama.com/download/mac).)*

- **Linux (Bash):**
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ```

### Step 2: Start the Ollama Service Daemon

In a dedicated terminal window, start the local Ollama server (port `11434`):

```bash
ollama serve
```
*(On Windows/macOS, if you installed the desktop tray app and it is already running, `ollama serve` may report the address is already in use — that means the daemon is already active.)*

### Step 3: Pull the Model Weights (~2.0 GB Download / ~2.2 GB on Disk)

In your terminal, pull the CodeStruct target model:

```bash
ollama pull qwen2.5-coder:3b
```

### Step 4: Verify Model Availability

```bash
ollama list
```
*(Expected output lists `qwen2.5-coder:3b`.)*

---

## Execution Guide

### Launching CodeStruct (Native Desktop Window)

Ensure your virtual environment `(venv)` is active and run from the repository root:

```bash
python run.py
```

### Startup Behavior:
1. FastAPI initializes and probes `http://localhost:11434/api/tags` (1-second timeout).
2. `find_available_port()` selects port `8000`, automatically falling back through `8001`–`8020` if occupied.
3. Uvicorn runs the local backend server in a background daemon thread.
4. `pywebview` opens the 1280×800 native desktop window.

### Analyzing Codebases:
- **Bundled Sample Project:** Click **Analyze** directly (leaving the path field empty or as `sample_project`) to inspect the built-in 16-node `sample_project/sample_project.py` fixture.
- **Any Local Repository:** Enter an absolute path (e.g., `C:\projects\my_repo` on Windows or `/Users/name/my_repo` on macOS/Linux) or a relative path, then click **Analyze**.

### Headless / Web Browser Mode (Alternative to Native Window):
If deploying on a headless server or preferring a standard browser over `pywebview`:

```bash
# Run from the repository root (note --app-dir codestruct is required):
python -m uvicorn backend.main:app --app-dir codestruct --host 127.0.0.1 --port 8000
```
Then open `http://127.0.0.1:8000` in your browser.

---

## Verification & Test Suite

With `(venv)` active at the repository root, run the automated verification suites.

### Run Complete Regression Suite (78 Tests)

```bash
python -m pytest -v
```
*(Expected output: `78 passed` covering AST analysis, FastAPI routes, cache invalidation, pattern heuristics, Phase 19 LLM validator safety net, Multi-LLM provider & encrypted storage, configuration & wizard, and Phase 20 SUS scoring.)*

### Run Individual Targeted Test Modules

```bash
# 1. Core AST Parser & Edge Extractor (7 tests)
python -m pytest -v codestruct/tests/test_analyzer.py

# 2. FastAPI Endpoints, Pygments Code Slices & Instability Metrics (25 tests)
python -m pytest -v codestruct/tests/test_api.py

# 3. Incremental Cache Hits & File Modification/Deletion Invalidation (4 tests)
python -m pytest -v codestruct/tests/test_cache.py

# 4. Design Pattern Heuristics: Singleton, Factory & Observer (8 tests)
python -m pytest -v codestruct/tests/test_patterns.py

# 5. Advanced Architecture Clustering & Validation Safety Net (8 tests)
python -m pytest -v codestruct/tests/test_advanced_architecture.py

# 6. Configuration & First-Run Wizard Tests (5 tests)
python -m pytest -v codestruct/tests/test_config_and_wizard.py

# 7. Multi-LLM Provider & Key Encryption Tests (8 tests)
python -m pytest -v codestruct/tests/test_multi_llm.py

# 8. Usability Study SUS Formula Unit Tests (13 tests)
python -m pytest -v docs/usability_study/test_score.py
```

---

## Core Feature Tour

### 1. Interactive Graph View (`Graph` Tab)
- **Cytoscape Canvas:** Interactive visualization of `module`, `class`, `function`, and `method` nodes.
- **Directed Edge Types:** `inherits` (inheritance), `defines` (containment), `constructs` (instantiation), and `calls` (invocations).
- **Controls:** Pan, zoom, fit to viewport, toggle layout (dagre vs cose), and filter checkboxes by node kind.

### 2. Tabular Symbols View (`Table` Tab)
- Multi-column sortable table listing every extracted symbol (Name, Kind, Module, File, Start Line, End Line).
- Clicking any row synchronizes focus across Explorer, Graph, and Inspector.

### 3. Design Patterns (`Patterns` Tab)
- Pure AST structural heuristics for **Singleton**, **Factory**, and **Observer** patterns.
- Displays exact AST heuristic evidence strings alongside a permanent disclaimer noting heuristic detection rather than guaranteed design intent.

### 4. Read-Only Code Viewer (`Code` Tab)
- Syntax-highlighted source slice rendered server-side via Pygments (`one-dark` theme) with ±5 lines of surrounding context.
- **Open in Editor:** Launches the file externally via your OS default handler (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux).

### 5. Advanced Architecture (`Architecture` Tab)
- Groups symbols into architectural component clusters with assigned roles, rationales, and a project-level narrative.
- **Validation Safety Net:** Drops and logs any hallucinated symbol IDs; recovers omitted real symbols into `Unclustered Symbols`.
- **Cross-Navigation:** Clicking any component switches to `Graph` view, highlights its member symbols, and loads the primary symbol in Inspector.

### 6. Collapsible 4-Dock Workspace
- **Explorer (Left):** Instant symbol filter tree; collapses to a 40px rail.
- **Inspector (Right Top):** Fan-in, fan-out, Robert C. Martin's Instability ($I = \frac{\text{fan-out}}{\text{fan-in} + \text{fan-out}}$), docstrings, relationships, and transitive change-impact blast radius; collapses to a 40px rail.
- **AI Assistant (Right Bottom):** Context-aware Ollama chat automatically receiving selected symbol metadata and source slices; collapses to a 40px rail.
- **Status & Logs (Bottom):** Real-time timings, parse warnings, and system alerts.

---

## REST API Reference

Endpoints exposed on `http://127.0.0.1:<port>`:

| Method | Endpoint | Request Body / Query | Response Model | Description |
|---|---|---|---|---|
| `POST` | `/api/analyze` | `{"project_path": "...", "force_refresh": false}` | `Graph` | Parses project or single `.py` file and caches graph state. |
| `GET` | `/api/symbol/{node_id}` | *Path param:* `node_id` | `SymbolDetail` | Symbol metadata, relationships, fan-in/out, and instability. |
| `GET` | `/api/source` | `?file_path=...&start=1&end=50` | `SourceResponse` | Pygments syntax-highlighted HTML slice. |
| `GET` | `/api/impact/{node_id}` | `?max_depth=5` | `ImpactResponse` | Reverse dependency blast radius via BFS. |
| `GET` | `/api/patterns` | *None* | `PatternsResponse` | Detected Singleton, Factory, and Observer matches. |
| `POST` | `/api/architecture/advanced` | `{"force_refresh": false}` | `AdvancedArchitectureResponse` | Validated LLM component clustering & architectural narrative. |
| `POST` | `/api/open_in_editor` | `{"file_path": "..."}` | `OpenInEditorResponse` | Opens file in OS default external editor. |
| `POST` | `/api/qwen/chat` | `{"message": "...", "context_symbol_id": "..."}` | `ChatResponse` | Context-grounded chat with local Ollama model. |
| `GET` | `/api/qwen/status` | *None* | `{"status": "connected"}` | Checks Ollama server reachability (`localhost:11434`). |
| `GET` | `/` | *None* | `FileResponse` | Serves desktop application shell (`index.html`). |

---

## Directory Structure & Functional Roles

```text
CodeStruct/
├── run.py                                  # Root execution entrypoint
├── requirements.txt                        # Universal pinned dependencies & local AI setup notice
├── README.md                               # Zero-friction onboarding & operational guide
├── CodeStruct_Project_Plan.md              # Master technical specification & data contracts
├── codestruct/
│   ├── run.py                              # Package-level secondary wrapper
│   ├── requirements.txt                    # Synchronized requirements file
│   ├── README.md                           # Synchronized package README
│   ├── backend/
│   │   ├── __init__.py                     # Package marker
│   │   ├── main.py                         # FastAPI lifecycle, port fallback & pywebview window
│   │   ├── analyzer.py                     # AST parser, edge extraction & change-impact BFS
│   │   ├── cache.py                        # Incremental SHA-256 AST disk cache manager
│   │   ├── config.py                       # Persistent AppData settings & cache paths
│   │   ├── llm_client.py                   # Multi-LLM query interface
│   │   ├── llm_providers.py                # Abstract LLM provider & concrete implementations
│   │   ├── model_config.py                 # Encrypted API key storage & model registry
│   │   ├── patterns.py                     # Singleton, Factory, Observer heuristic detectors
│   │   ├── qwen_client.py                  # Ollama REST client & context prompt builder
│   │   ├── advanced_architecture.py        # Component clustering, validation net & caching
│   │   ├── schemas.py                      # Pydantic v2 models & validation contracts
│   │   └── wizard.py                       # First-run system check & environment wizard
│   ├── frontend/
│   │   ├── index.html                      # Desktop semantic shell & 4-dock workspace
│   │   └── static/
│   │       ├── app.js                      # UI controller, Cytoscape renderer & selection sync
│   │       ├── app.css                     # Blueprint dark theme stylesheet & icon rails
│   │       └── vendor/                     # Vendored offline assets (zero CDN dependencies)
│   │           ├── cytoscape.min.js        # Cytoscape.js 3.28.1
│   │           └── fonts/                  # Inter & JetBrains Mono WOFF2 fonts
│   ├── sample_project/
│   │   └── sample_project.py               # Fixed 16-node test fixture (do not modify)
│   └── tests/
│       ├── test_analyzer.py                # AST extraction unit tests
│       ├── test_api.py                     # API integration tests
│       ├── test_cache.py                   # Cache hit & modify/delete invalidation tests
│       ├── test_config_and_wizard.py       # Configuration & wizard unit tests
│       ├── test_multi_llm.py               # Multi-LLM provider & encryption tests
│       ├── test_patterns.py                # Pattern heuristic fixture & negative control tests
│       ├── test_advanced_architecture.py   # LLM validator safety net & retry tests
│       ├── cache_fixtures/                 # 2-file cross-file invalidation fixture
│       └── pattern_fixtures/               # Singleton/Factory/Observer example fixtures
├── docs/
│   └── usability_study/                    # Phase 20 Usability Study Tooling
│       ├── questionnaire.html              # Offline 10-item SUS questionnaire
│       ├── score.py                        # SUS & rubric computation script
│       ├── test_score.py                   # 13 SUS unit tests
│       ├── results.md                      # Study reporting template
│       └── raw_data/                       # Participant JSON-lines schema & data directory
└── .codestruct_cache/                      # Generated AST cache (gitignored)
```

---

## Troubleshooting & Common Pitfalls

### 1. Port Already in Use (`[Errno 10048]` on Windows / `[Errno 98]` on Linux/macOS)
- **Cause:** Another process is already bound to port `8000`.
- **Solution:** Launching via `python run.py` resolves this automatically via `find_available_port()`, binding to `8001`–`8020`. If running Uvicorn directly in headless mode, pass an alternate port:
  ```bash
  python -m uvicorn backend.main:app --app-dir codestruct --host 127.0.0.1 --port 8080
  ```

### 2. PowerShell Script Execution Policy (`PSSecurityException`)
- **Cause:** Windows PowerShell blocks unsigned scripts by default, preventing `.\venv\Scripts\Activate.ps1`.
- **Solution:** Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` in your PowerShell session before activating the virtual environment.

### 3. `ModuleNotFoundError: No module named 'backend'` When Running Uvicorn
- **Cause:** Running Uvicorn directly from root without `--app-dir codestruct`.
- **Solution:** Always run `python run.py` or pass `--app-dir codestruct` to Uvicorn:
  `python -m uvicorn backend.main:app --app-dir codestruct --host 127.0.0.1 --port 8000`

### 4. Qwen Assistant Shows `Disconnected`
- **Cause:** Ollama service is not running on port `11434`.
- **Solution:** Start `ollama serve` in a terminal, pull the model (`ollama pull qwen2.5-coder:3b`), and verify `ollama list`.

### 5. Linux `pywebview` Fails to Open Window
- **Cause:** Missing GTK/WebKitGTK bindings or running on a headless SSH session without `$DISPLAY`.
- **Solution:** Install GTK/WebKit system packages (`sudo apt-get install -y python3-gi gir1.2-webkit2-4.1`), or launch in headless browser mode via Uvicorn and forward port `8000`.

### 6. Target Project Has Syntax Errors
- **Behavior:** CodeStruct catches `SyntaxError` safely per file, records the diagnostic in `errors`, displays a warning in Status/Logs, and still graphs all valid files.

---

## License

CodeStruct is open-source software licensed under the MIT License.
