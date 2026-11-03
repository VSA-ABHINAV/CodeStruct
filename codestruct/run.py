import sys
from pathlib import Path

# Ensure package directory is on sys.path
package_dir = Path(__file__).resolve().parent
if str(package_dir) not in sys.path:
    sys.path.insert(0, str(package_dir))

from backend.main import start

if __name__ == "__main__":
    start()
