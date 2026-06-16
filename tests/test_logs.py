import json

from socio_sim.config import RunConfig
from socio_sim.logs.events import EventLog
from socio_sim.logs.manifest import Manifest
from socio_sim.logs.replay import verify


def make_log(events):
    log = EventLog()
    for e in events:
        log.append(**e)
    return log


EVENTS = [
    dict(tick=0, kind="post", actor_id=1, content_id="c1", data={"topic": 2}),
    dict(tick=1, kind="moderation", actor_id=-1, content_id="c1",
         data={"rule_id": "EU-ILLEGAL-1", "action": "remove",
               "decision_rationale": "score 0.97 >= threshold 0.9"}),
]


def test_stream_hash_stable_and_sensitive():
    a, b = make_log(EVENTS), make_log(EVENTS)
    assert a.stream_hash() == b.stream_hash()
    mutated = [dict(EVENTS[0]), dict(EVENTS[1])]
    mutated[1]["data"] = dict(mutated[1]["data"], action="label")
    c = make_log(mutated)
    assert c.stream_hash() != a.stream_hash()


def test_jsonl_append_only_and_readable(tmp_path):
    path = tmp_path / "events.jsonl"
    log = EventLog(path=path)
    log.append(**EVENTS[0])
    log.flush()
    # Readable mid-run (append-only, line-delimited)
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["kind"] == "post"
    log.append(**EVENTS[1])
    log.flush()
    assert len(path.read_text().strip().splitlines()) == 2


def test_manifest_round_trip(tmp_path):
    cfg = RunConfig.test()
    m = Manifest.create(cfg, pack_versions={"eu_dsa": "1.0"})
    p = tmp_path / "manifest.json"
    m.save(p)
    again = Manifest.load(p)
    assert again.config_hash == cfg.config_hash()
    assert again.root_seed == cfg.root_seed
    assert again.pack_versions == {"eu_dsa": "1.0"}


def test_replay_verify_detects_match_and_divergence(tmp_path):
    cfg = RunConfig.test()
    m = Manifest.create(cfg, pack_versions={})

    def run_same(config):
        return make_log(EVENTS)

    def run_diff(config):
        return make_log(EVENTS[:1])

    original = make_log(EVENTS)
    ok, _ = verify(m, original.stream_hash(), run_same)
    assert ok
    bad, summary = verify(m, original.stream_hash(), run_diff)
    assert not bad
    assert "mismatch" in summary
