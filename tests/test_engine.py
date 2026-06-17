import pytest

from socio_sim.config import RunConfig
from socio_sim.engine import Simulation
from socio_sim.logs.replay import verify


def boosted_rates():
    """Higher harmful-content base rates so a 200x48 test run exercises
    the moderation pipeline reliably."""
    rates = dict(RunConfig.test().category_base_rates)
    rates.update({"misinfo": 0.15, "hate": 0.05})
    return rates


@pytest.fixture(scope="module")
def result():
    cfg = RunConfig.test(jurisdictions=("EU",),
                         category_base_rates=boosted_rates())
    return Simulation(cfg).run()


def test_smoke_event_kinds_present(result):
    kinds = {e["kind"] for e in result.log.events}
    for expected in ("post", "classify", "impression", "engagement",
                     "moderation", "ad_auction"):
        assert expected in kinds, f"missing event kind {expected}"


def test_manifest_valid(result):
    m = result.manifest
    assert m.config_hash == RunConfig.from_dict(m.config).config_hash()
    assert "eu_dsa" in m.pack_versions
    assert m.stream_hash == result.log.stream_hash()


def test_same_seed_identical_stream():
    cfg = RunConfig.test(jurisdictions=("EU",),
                         category_base_rates=boosted_rates())
    h1 = Simulation(cfg).run().log.stream_hash()
    h2 = Simulation(cfg).run().log.stream_hash()
    assert h1 == h2


def test_different_seed_different_stream(result):
    cfg = RunConfig.test(jurisdictions=("EU",), root_seed=999,
                         category_base_rates=boosted_rates())
    assert Simulation(cfg).run().log.stream_hash() != result.log.stream_hash()


def test_replay_verifier_passes(result):
    def run_fn(config_dict):
        return Simulation(RunConfig.from_dict(config_dict)).run().log

    ok, summary = verify(result.manifest, result.log.stream_hash(), run_fn)
    assert ok, summary


def test_run_writes_outputs(tmp_path):
    cfg = RunConfig.test(out_dir=str(tmp_path))
    Simulation(cfg).run(write=True)
    assert (tmp_path / "events.jsonl").exists()
    assert (tmp_path / "manifest.json").exists()
