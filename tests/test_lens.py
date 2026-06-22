"""Run-lens labelling: the report + payload must state which decision lens
(Government/Regulatory vs Marketing) is active and what the output means."""

from socio_sim.analytics.lens import SETTING_LENS, run_lens
from socio_sim.config import RunConfig
from socio_sim.pipeline import run_and_analyze


def test_marketing_lens_tracks_ads_flag():
    on = run_and_analyze(RunConfig.test(jurisdictions=("EU",), ads_enabled=True),
                         verify_replay=False)
    off = run_and_analyze(RunConfig.test(jurisdictions=("US",), ads_enabled=False),
                          verify_replay=False)
    assert run_lens(on.result.config.to_dict(), on.summary)["marketing_active"] is True
    assert run_lens(off.result.config.to_dict(), off.summary)["marketing_active"] is False
    # government lens is always active (a jurisdiction pack is always present)
    assert run_lens(on.result.config.to_dict(), on.summary)["government_active"] is True


def test_lens_packs_reflect_jurisdictions_and_ftc():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU", "US"), ftc_enabled=True),
                        verify_replay=False)
    lens = run_lens(a.result.config.to_dict(), a.summary)
    assert any("EU" in p for p in lens["packs"]) and any("US" in p for p in lens["packs"])
    assert "FTC" in lens["packs"]


def test_report_contains_lens_and_interpretation():
    a = run_and_analyze(RunConfig.test(jurisdictions=("EU",), ads_enabled=True),
                        verify_replay=False)
    assert "Run lens & output interpretation" in a.report_md
    assert "Government / Regulatory lens" in a.report_md
    assert "Marketing lens" in a.report_md


def test_every_setting_tagged_to_a_known_lens():
    assert set(SETTING_LENS.values()) <= {"government", "marketing", "core"}
    for key in ("jurisdictions", "ads_enabled", "graph_kind"):
        assert key in SETTING_LENS
