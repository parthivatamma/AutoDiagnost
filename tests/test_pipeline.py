import json

from autodiag.knowledge import KnowledgeStore
from autodiag.obd import SimulatedReader
from autodiag.reasoning import diagnose
from autodiag.rules import evaluate


def test_fixture_scan_and_safety_rule() -> None:
    snapshot = SimulatedReader("fixtures/p0301.json").read_snapshot()
    assert snapshot.dtcs[0].code == "P0301"
    result = diagnose(snapshot)
    assert result.severity.value == "limit_driving"
    assert result.safety_notes


def test_knowledge_ingest_is_idempotent(tmp_path) -> None:
    source = tmp_path / "manual.md"
    source.write_text("# P0301\nSwap the ignition coil.\n")
    store = KnowledgeStore(tmp_path / "kb.sqlite")
    assert store.ingest([source]) == 1
    assert store.ingest([source]) == 0
    assert store.search("P0301 coil")


def test_fixture_payload_is_json_serializable() -> None:
    snapshot = SimulatedReader("fixtures/p0171.json").read_snapshot()
    json.dumps(snapshot.to_json_dict())
    assert "positive fuel trims suggest lean operation" in evaluate(snapshot)["flags"]
