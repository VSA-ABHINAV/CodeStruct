from pathlib import Path

Path(__file__).with_name("CODESTRUCT_FIXTURE_EXECUTED").write_text(
    "executed", encoding="utf-8"
)
raise RuntimeError("analyzed source was executed")
