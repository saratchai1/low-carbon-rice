from pathlib import Path

from app.services.catalog import bounds_intersect, sha256_file


class DemoPlot:
    center_lon = 100.274733
    center_lat = 14.469728


def test_sha256_is_reproducible(tmp_path: Path) -> None:
    source = tmp_path / "scene.tif"
    source.write_bytes(b"evidence-bytes")
    assert sha256_file(source) == sha256_file(source)
    assert len(sha256_file(source)) == 64


def test_footprint_intersection() -> None:
    assert bounds_intersect([100.27, 14.46, 100.28, 14.48], DemoPlot())
    assert not bounds_intersect([101.0, 15.0, 101.1, 15.1], DemoPlot())

