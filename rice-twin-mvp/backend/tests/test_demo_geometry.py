from app.seed import DEMO_CENTER_LAT, DEMO_CENTER_LON, DEMO_RING


def test_demo_geometry_uses_geojson_lon_lat_order() -> None:
    assert DEMO_RING[0] == DEMO_RING[-1]
    assert 100 < DEMO_CENTER_LON < 101
    assert 14 < DEMO_CENTER_LAT < 15
    assert all(100 < point[0] < 101 and 14 < point[1] < 15 for point in DEMO_RING)
