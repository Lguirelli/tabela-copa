from pathlib import Path

from scripts.ci_preflight import sha256


def test_sha256_is_stable(tmp_path: Path):
    path = tmp_path / "sample.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    assert sha256(path) == sha256(path)
    assert len(sha256(path)) == 64
