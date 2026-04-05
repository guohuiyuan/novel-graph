from novel_graph.analysis.keywords import infer_depress_points, infer_thunder_points


def test_infer_thunder_and_depress_points() -> None:
    text = "前世线出现背叛和非初争议，但没有绿帽。"
    thunder = infer_thunder_points(text)
    depress = infer_depress_points(text)

    thunder_names = {item.name for item in thunder}
    depress_names = {item.name for item in depress}

    assert "背叛" in thunder_names
    assert "px/fc/非初" in depress_names
