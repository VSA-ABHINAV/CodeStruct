# Platform support status

The package metadata declares Python 3.10–3.14 and a pure-Python wheel. Windows 11 with Python 3.14.6 and Node 24.18.0 is the only fully executed host in the current evidence. Paths containing spaces and non-ASCII characters are included in clean-install validation.

Linux and macOS jobs are prepared in CI to exercise packaging, scanning/path rules, SQLite, process spawning, CLI, and static serving, but support must not be claimed until those jobs run successfully. Container configuration targets Linux but is also unvalidated when Docker is unavailable. Browser support remains limited by the Phase 12 manual matrix; real screen readers and 125%/200% zoom are pending.
