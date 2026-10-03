# Building release artifacts

## Toolchain and output

Use Python 3.10–3.14, Node 24.18 (or a Vite-supported Node release), and the locked npm tree. On Windows PowerShell:

```powershell
python -m pip install -e ".[dev,release]"
python tools/release_candidate.py
```

`tools/build_release.py` copies source into a verified temporary staging directory, runs `npm ci` and the Vite build with `/app/`, stages assets only in that copy, builds with setuptools, and calls `tools/verify_artifacts.py`. It writes only ignored `release-output/` artifacts and always removes its verified staging directory. Do not use `--skip-npm-ci` for a candidate.

The wheel embeds hashed frontend assets and installs without Node. A fresh source-checkout release build requires Node/npm. The sdist contains the reviewed generated assets, so a wheel can be built from it with Python build tooling and no Node; rebuilding those assets requires the source checkout process.

Expected files are `codestruct-0.1.0.dev0-py3-none-any.whl`, `codestruct-0.1.0.dev0.tar.gz`, and `SHA256SUMS.json`. The verifier rejects caches, databases, environment files, source maps, test output, private-key markers, private Windows paths, or missing package/static content.

Linux/macOS commands use the same Python scripts and `python3`; they are CI preparation, not validated support until those jobs pass.
