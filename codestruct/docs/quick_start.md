# CodeStruct Quick Start Guide

Welcome to CodeStruct! This guide will help you run the app and explore a Python project's structure.

## Getting Started

### 1. Install Dependencies
Make sure you have Python 3.10+ installed. Install the required packages:

```powershell
pip install fastapi uvicorn pywebview pygments requests pytest
```

### 2. Start the Application
From the CodeStruct project folder, run:

```powershell
python run.py
```

A single native window will open displaying the CodeStruct interface.

### 3. Analyze a Project
Inside the app:

- **Top Toolbar**: Click the **"Analyze"** button.
- **Project Path**: The default project path is `sample_project` (the folder next to this README). If you want to analyze a different folder, enter its absolute or relative path.
- **Result**: The app will parse the Python files in the project and render an interactive graph showing modules, classes, functions, methods, and their relationships.

### 4. Exploring the Interface

| Panel | What you'll see |
|-------|----------------|
| **Left Dock (Explorer)** | A tree showing your project's files and symbols. Click any item to highlight it in the graph. |
| **Center Area** | The Cytoscape.js graph. Nodes are colored by type (modules, classes, functions, methods). Edges show relationships (inherits, defines, constructs, calls). Use pan, zoom, and fit controls. |
| **Right Docks** | **Inspector**: Select a symbol to see its details, fan-in/fan-out, and incoming/outgoing relationships. <br> **Qwen Assistant**: Chat with the local AI, with selected symbol context injected into prompts. |
| **Bottom Area** | **Log Panel**: Shows warnings for files that couldn't be parsed. <br> **Status Bar**: Displays node count / edge count (e.g., "16 nodes / 22 edges"). |

### 5. Using the Qwen Assistant
- Select any symbol in the graph or Explorer tree.
- Type a message like "explain this" in the Qwen chat panel.
- Press **Send**. The AI will reply using the selected symbol's details as context.
- If the Ollama server is not running, you'll see a "Disconnected" indicator and an error message.

### 6. Jump to Source
- Select a symbol in the graph or Explorer.
- Click the **"Jump to Source"` button** in the Inspector panel.
- The Code Viewer tab will open, showing syntax-highlighted source code with the symbol's line range highlighted.

### 7. Closing the App
- Close the native window.
- The process will exit cleanly — no orphaned background processes will remain.

## Need Help?
- If you get an error saying "Ollama is not running", make sure Ollama is installed and `qwen2.5-coder:3b` is pulled (`ollama pull qwen2.5-coder:3b`).
- If the graph doesn't render, make sure you've analyzed a valid Python project directory.

---
*CodeStruct — Static Python project analysis, one window, no embedded IDE.*