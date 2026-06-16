import numpy as np

from socio_sim.rng import SeedTree


def test_same_key_same_stream():
    t = SeedTree(123)
    a = t.generator("agents", replicate=3).random(10)
    b = t.generator("agents", replicate=3).random(10)
    assert np.array_equal(a, b)


def test_different_module_independent_stream():
    t = SeedTree(123)
    a = t.generator("agents", replicate=0).random(10)
    b = t.generator("content", replicate=0).random(10)
    assert not np.array_equal(a, b)


def test_different_replicate_and_seed_differ():
    t = SeedTree(123)
    assert not np.array_equal(
        t.generator("feed", 0).random(10), t.generator("feed", 1).random(10)
    )
    assert not np.array_equal(
        SeedTree(1).generator("feed", 0).random(10),
        SeedTree(2).generator("feed", 0).random(10),
    )
