"""Optional GPU acceleration backend: verified on the numpy path (CI has no GPU)."""

import numpy as np

from socio_sim.accel import array_module, to_numpy, using_gpu


def test_array_module_defaults_to_numpy_without_a_gpu():
    assert array_module() is np
    assert using_gpu() is False


def test_to_numpy_is_identity_for_numpy_arrays():
    a = np.arange(6)
    assert to_numpy(a) is a


def test_classifier_explicit_numpy_xp_matches_auto():
    from socio_sim.config import CATEGORIES
    from socio_sim.content.ml_classifier import TrainableClassifier
    texts = ["free money claim prize", "normal day at the park",
             "breaking exposed coverup", "lovely weather today"] * 8
    labels = [{"fraud"}, set(), {"misinfo"}, set()] * 8
    auto = TrainableClassifier(CATEGORIES, epochs=40).fit(texts, labels)
    explicit = TrainableClassifier(CATEGORIES, epochs=40, xp=np).fit(texts, labels)
    assert auto.predict_scores(texts[0]) == explicit.predict_scores(texts[0])
