
import numpy as np

from app.services import reward_model as rm

from conftest import DOCUMENT


def test_features_in_expected_range():
    x = rm.features(DOCUMENT, "Solar costs dropped by about 90%. China leads manufacturing.")
    assert x.shape == (len(rm.FEATURES),)
    assert np.all(x >= 0) and np.all(x <= 2)


def test_invented_numbers_lower_the_reward():
    model = rm.RewardModel()
    faithful = "Solar costs dropped by about 90% over the last decade."
    invented = "Solar costs dropped by about 75% over the last decade."
    assert model.score(DOCUMENT, faithful) > model.score(DOCUMENT, invented)


def test_repetition_lowers_the_reward():
    model = rm.RewardModel()
    once = "Solar power is growing fast worldwide and costs have dropped."
    repeated = once + " " + once + " " + once
    assert model.score(DOCUMENT, once) > model.score(DOCUMENT, repeated)


def test_fit_is_stable_on_extreme_data():
    # Large, correlated features used to make training diverge.
    rng = np.random.default_rng(0)
    rated = [(rng.uniform(0, 2, len(rm.FEATURES)), r) for r in [1, 2, 2, 5, 1] * 20]
    pairs = [(rng.uniform(0, 2, len(rm.FEATURES)), rng.uniform(0, 2, len(rm.FEATURES)))
             for _ in range(50)]
    w, b = rm._fit(rated, pairs)
    assert np.all(np.isfinite(w)) and np.isfinite(b)
    assert np.all(np.abs(w) < 20)


def test_fit_learns_from_preferences():
    coverage = rm.FEATURES.index("coverage")
    win = np.zeros(len(rm.FEATURES))
    win[coverage] = 1.0
    lose = np.zeros(len(rm.FEATURES))
    w, _ = rm._fit([], [(win, lose)] * 30)
    assert w[coverage] > rm.PRIOR_WEIGHTS[coverage]


def test_best_picks_highest_reward():
    model = rm.RewardModel()
    good = "Solar costs dropped by about 90%, and China leads panel manufacturing."
    bad = "Things happened. Things happened. Things happened."
    best, _ = model.best(DOCUMENT, [bad, good, ""])
    assert best == good
