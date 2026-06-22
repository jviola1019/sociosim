"""Stylized-facts validation: the simulator must reproduce documented empirical
regularities (face validity), deterministically, with cited sources."""

from socio_sim.config import RunConfig
from socio_sim.validation.stylized import PROVENANCE, evaluate_stylized_facts


def _cfg():
    # The realistic (Holme–Kim) configuration, modest scale for a fast test.
    return RunConfig.test(jurisdictions=("EU",), n_agents=400, n_ticks=120,
                          graph_kind="plc", graph_params={"m": 5, "p": 0.7})


def test_calibrated_world_reproduces_all_stylized_facts():
    res = evaluate_stylized_facts(_cfg())
    assert res["provenance"] == PROVENANCE
    assert res["n_total"] == 5
    failed = [f["name"] for f in res["facts"] if not f["passes"]]
    assert not failed, f"stylized facts failed: {failed}"


def test_each_fact_is_cited_and_well_formed():
    res = evaluate_stylized_facts(_cfg())
    names = {f["name"] for f in res["facts"]}
    assert {"heavy_tailed_degree", "clustering_exceeds_random", "cascade_right_skew",
            "participation_inequality", "diurnal_cycle"} == names
    for f in res["facts"]:
        assert f["source"] and f["lo"] is not None        # every fact cites a source + band
        assert isinstance(f["passes"], bool)


def test_stylized_facts_are_deterministic():
    a = evaluate_stylized_facts(_cfg())
    b = evaluate_stylized_facts(_cfg())
    assert [f["observed"] for f in a["facts"]] == [f["observed"] for f in b["facts"]]
