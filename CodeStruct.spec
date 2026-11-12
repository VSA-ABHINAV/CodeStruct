# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for standalone Windows CodeStruct.exe (single-file, no console)."""

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

block_cipher = None

# Collect package assets & dynamic submodules cleanly
webview_datas, webview_binaries, webview_hidden = collect_all("webview")
pythonnet_datas, pythonnet_binaries, pythonnet_hidden = collect_all("pythonnet")
clr_datas, clr_binaries, clr_hidden = collect_all("clr_loader")

uvicorn_hidden = collect_submodules("uvicorn")
pygments_hidden = [
    "pygments.lexers.python",
    "pygments.styles.onedark",
    "pygments.formatters.html",
]

datas = [
    ("codestruct/frontend", "frontend"),
    ("codestruct/sample_project", "sample_project"),
] + webview_datas + pythonnet_datas + clr_datas

binaries = webview_binaries + pythonnet_binaries + clr_binaries

hiddenimports = (
    [
        "backend",
        "backend.config",
        "backend.wizard",
        "backend.main",
        "backend.api",
        "backend.analyzer",
        "backend.cache",
        "backend.patterns",
        "backend.qwen_client",
        "backend.advanced_architecture",
        "backend.schemas",
        "backend.llm_client",
        "backend.llm_providers",
        "backend.model_config",
        "anyio._backends._asyncio",
        "clr",
        "cryptography",
        "cryptography.fernet",
    ]
    + uvicorn_hidden
    + pygments_hidden
    + webview_hidden
    + pythonnet_hidden
    + clr_hidden
)

# Exclude heavy unrelated global packages so CodeStruct.exe stays compact (< 150 MB)
excludes = [
    "torch",
    "torchaudio",
    "torchvision",
    "tensorflow",
    "keras",
    "tensorboard",
    "scipy",
    "numpy",
    "pandas",
    "matplotlib",
    "sklearn",
    "scikit-learn",
    "xgboost",
    "lightgbm",
    "cv2",
    "opencv-python",
    "PIL",
    "Pillow",
    "pygame",
    "IPython",
    "ipykernel",
    "jupyter",
    "jupyterlab",
    "notebook",
    "jedi",
    "parso",
    "tkinter",
    "_tkinter",
    "pytest",
    "langchain",
    "langchain_core",
    "langchain_ollama",
    "langsmith",
    "sqlalchemy",
    "lxml",
    "bs4",
    "beautifulsoup4",
    "h5py",
    "netCDF4",
    "grpc",
    "ollama",
    "websockets",
    "pyzmq",
    "tornado",
    "sphinx",
]

a = Analysis(
    ["run.py"],
    pathex=[".", "codestruct"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CodeStruct",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

