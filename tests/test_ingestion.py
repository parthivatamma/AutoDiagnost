from autodiag.ingestion import (
    SnapshotData,
    extract_features,
    parse_symptoms,
    run_diagnosis,
)
from pydantic import ValidationError


PAYLOAD = {
    "vehicle": {
        "year": 2014,
        "make": "Honda",
        "model": "Accord",
        "engine": "2.4L K24W I4",
        "mileage": 128400,
    },
    "codes": {"stored": ["P0301"], "pending": ["P0300"]},
    "freeze_frame": {
        "rpm": 742,
        "load_pct": 21.6,
        "coolant_c": 88,
        "stft_pct": 6.2,
        "ltft_pct": 3.9,
        "map_kpa": 31,
        "speed_kmh": 0,
        "throttle_pct": 12.5,
    },
    "live_data": {
        "rpm": 715,
        "coolant_c": 91,
        "intake_c": 34,
        "stft_pct": 5.5,
        "ltft_pct": 4.7,
        "maf_gs": 3.1,
        "map_kpa": 33,
        "timing_deg": 9.5,
        "o2_up_v": 0.42,
        "o2_down_v": 0.68,
    },
    "symptoms": (
        "Rough idle and a shake at stoplights, worse when cold. "
        "Check engine light flashed once on the highway then stayed on."
    ),
}


def test_payload_validates_and_extracts_total_fuel_trim() -> None:
    snapshot = SnapshotData.model_validate(PAYLOAD)
    features = extract_features(snapshot)
    assert features.at[0, "freeze_total_fuel_trim_pct"] == 10.1
    assert features.at[0, "live_total_fuel_trim_pct"] == 10.2


def test_symptom_parser_extracts_categorical_flags() -> None:
    result = parse_symptoms(PAYLOAD["symptoms"])
    assert result == {
        "temperature_state": "cold",
        "idle_quality": "rough",
        "warning_light": "flashing",
        "is_misfire_cold": True,
        "flashing_cel": True,
    }


def test_run_diagnosis_uses_validated_snapshot() -> None:
    result = run_diagnosis(PAYLOAD)
    assert "Urgent misfire risk" in result
    assert "P0301" in result


def test_invalid_snapshot_is_rejected() -> None:
    invalid = {**PAYLOAD, "vehicle": {**PAYLOAD["vehicle"], "mileage": -1}}
    try:
        SnapshotData.model_validate(invalid)
    except ValidationError as error:
        assert "mileage" in str(error)
    else:
        raise AssertionError("invalid mileage was accepted")
