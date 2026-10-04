from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted(p for d in ("src", "tests", "benchmarks") for p in (ROOT / d).rglob("*.py"))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_source_has_no_control_characters(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    bad = sorted({hex(ord(c)) for c in text if ord(c) < 32 and c not in "\n\t\r"})
    assert not bad, f"control characters {bad} in {path}"
