from datetime import datetime, timezone

from autodiag import DTC, SnapshotSource, VehicleSnapshot


def test_snapshot_normalizes_dtc_and_omits_blank_symptoms() -> None:
    snapshot = VehicleSnapshot(
        source=SnapshotSource.FIXTURE,
        dtcs=[DTC(code=" p0301 ", description="Cylinder 1 misfire")],
        symptoms=[" rough idle ", "", "  "],
    )

    assert snapshot.dtcs[0].code == "P0301"
    assert snapshot.symptoms == ["rough idle"]


def test_snapshot_redacts_vin_without_mutating_original() -> None:
    snapshot = VehicleSnapshot(
        captured_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source=SnapshotSource.ADAPTER,
        vehicle={"vin": "1HGBH41JXMN109186"},
    )

    redacted = snapshot.redacted()

    assert snapshot.vehicle.vin == "1HGBH41JXMN109186"
    assert redacted.vehicle.vin == "[REDACTED]"
    assert redacted.to_json_dict()["source"] == "adapter"
