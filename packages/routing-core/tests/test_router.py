from umbrastride_routing.weights import edge_weight, shade_bias_for_alpha


def test_edge_weight_alpha_one_is_length():
    assert edge_weight(100.0, 0.0, 1.0) == 100.0


def test_edge_weight_alpha_zero_favors_shade():
    w_sunny = edge_weight(100.0, 0.0, 0.0, beta=2.0)
    w_shady = edge_weight(100.0, 1.0, 0.0, beta=2.0)
    assert w_shady < w_sunny


def test_edge_weight_alpha_zero_prioritizes_shade_over_distance(monkeypatch):
    monkeypatch.setenv("SHADE_DISTANCE_TIEBREAK", "0.001")
    short_sunny = edge_weight(1.0, 0.0, 0.0, beta=5.0)
    long_shaded = edge_weight(1000.0, 1.0, 0.0, beta=5.0)
    assert long_shaded < short_sunny


def test_shade_bias_curve_keeps_midpoint_from_saturating(monkeypatch):
    monkeypatch.setenv("SHADE_BIAS_CURVE", "3.0")
    assert shade_bias_for_alpha(0.0) == 1.0
    assert shade_bias_for_alpha(1.0) == 0.0
    assert shade_bias_for_alpha(0.5) == 0.125


def test_edge_weight_mixed_alpha_between():
    w = edge_weight(100.0, 0.5, 0.5, beta=2.0)
    assert 50 < w < 150
