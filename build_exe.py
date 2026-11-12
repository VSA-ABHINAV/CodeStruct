"""Build script for CodeStruct standalone Windows executable."""

import os
import subprocess
import sys
from pathlib import Path

def build():
    root_dir = Path(__file__).resolve().parent
    spec_file = root_dir / "CodeStruct.spec"
    dist_exe = root_dir / "dist" / "CodeStruct.exe"

    if not spec_file.exists():
        print(f"[Error] Spec file not found: {spec_file}")
        sys.exit(1)

    print(f"[*] Starting PyInstaller build using {spec_file.name}...")
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "-y", str(spec_file)]
    res = subprocess.run(cmd, cwd=str(root_dir))

    if res.returncode != 0:
        print(f"[Error] PyInstaller build failed with exit code {res.returncode}")
        sys.exit(res.returncode)

    if not dist_exe.is_file():
        print(f"[Error] Expected executable was not found at {dist_exe}")
        sys.exit(1)

    size_bytes = dist_exe.stat().st_size
    size_mb = size_bytes / (1024 * 1024)
    print(f"[+] Successfully built: {dist_exe}")
    print(f"[+] File size: {size_mb:.2f} MB ({size_bytes:,} bytes)")

    max_mb = 150.0
    if size_mb > max_mb:
        print(f"[Error] File size {size_mb:.2f} MB exceeds limit of {max_mb} MB")
        sys.exit(1)

    print(f"[+] Size verification passed: {size_mb:.2f} MB < {max_mb} MB")
    return dist_exe

if __name__ == "__main__":
    build()

