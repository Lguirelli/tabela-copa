from pathlib import Path

from scripts.build_static_site import build


def test_static_build_excludes_repository_internals(tmp_path: Path) -> None:
    output = tmp_path / "site"
    summary = build(output)
    assert summary["html_files"] >= 1
    assert (output / "index.html").is_file()
    assert (output / "src" / "model-pages.js").is_file()
    assert not (output / ".github").exists()
    assert not (output / "data").exists()
    assert not (output / "models").exists()
