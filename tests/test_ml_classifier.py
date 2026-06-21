"""Real trainable moderation classifier: it must LEARN category signal from
generated text and achieve measured (not assumed) precision/recall, and be
deterministic."""

import numpy as np

from socio_sim.agents.personas import Personas
from socio_sim.config import CATEGORIES, RunConfig
from socio_sim.content.generate import TemplateGenerator
from socio_sim.content.ml_classifier import (TrainableClassifier,
                                             build_training_data, evaluate,
                                             vectorize)
from socio_sim.rng import SeedTree


def _generator(seed=3, n_personas=60):
    rates = dict(RunConfig().category_base_rates)
    rates.update({"misinfo": 0.3, "fraud": 0.3, "hate": 0.3})  # enough positives
    cfg = RunConfig.test(category_base_rates=rates)
    personas = Personas.sample(n_personas, np.ones(n_personas),
                               SeedTree(seed).generator("agents", 0), cfg.n_topics)
    gen = TemplateGenerator(cfg, SeedTree(seed).generator("content", 0),
                            inject_signal=True)
    return gen, personas


def test_vectorize_is_stable_and_deterministic():
    a = vectorize("free money claim prize", 256)
    b = vectorize("free money claim prize", 256)
    assert (a == b).all() and a.sum() == 4.0       # 4 tokens counted


def test_trained_classifier_learns_with_measured_precision_recall():
    gen, personas = _generator()
    texts, labels = build_training_data(gen, personas, n=2000)
    xtr, ltr, xte, lte = texts[:1600], labels[:1600], texts[1600:], labels[1600:]
    clf = TrainableClassifier(CATEGORIES, epochs=300).fit(xtr, ltr)
    ev = evaluate(clf, xte, lte)
    for c in ("misinfo", "fraud", "hate"):
        assert ev[c]["support"] > 0, c
        assert ev[c]["recall"] >= 0.7, (c, ev[c])      # MEASURED, learned signal
        assert ev[c]["precision"] >= 0.7, (c, ev[c])


def test_trained_classifier_is_deterministic():
    gen, personas = _generator()
    texts, labels = build_training_data(gen, personas, n=400)
    a = TrainableClassifier(CATEGORIES, epochs=50).fit(texts, labels)
    b = TrainableClassifier(CATEGORIES, epochs=50).fit(texts, labels)
    assert a.predict_scores(texts[0]) == b.predict_scores(texts[0])
