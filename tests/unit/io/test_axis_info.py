from phage_annotator.io import parse_axes_info


def test_parse_axes_info_with_channels() -> None:
    info = parse_axes_info((2, 3, 4, 5), ome_axes="TCYX")
    assert info["channel_count"] == 3
    assert info["tzyx"] == (2, 1, 4, 5)
    assert info["has_time"] is True
    assert info["has_z"] is False
    assert info["source"] == "ome"
    assert info["inferred"] is False


def test_parse_axes_info_heuristic_time() -> None:
    info = parse_axes_info((3, 4, 5), interpret_3d_as="auto")
    assert info["axes"] == "TYX"
    assert info["tzyx"] == (3, 1, 4, 5)
    assert info["source"] == "heuristic"
