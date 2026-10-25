"""Validated structured snapshot ingestion and model-ready feature extraction."""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

FEATURE_COLUMNS = [
    "RPM",
    "Engine_Load_pct",
    "Short_Term_Fuel_Trim_pct",
    "Long_Term_Fuel_Trim_pct",
    "MAF_g_s",
]


class Vehicle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=1886, le=2100)
    make: str = Field(min_length=1)
    model: str = Field(min_length=1)
    engine: str = Field(min_length=1)
    mileage: float = Field(ge=0)


class Codes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stored: list[str] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)

    @field_validator("stored", "pending")
    @classmethod
    def normalize_codes(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            code = value.strip().upper()
            if not re.fullmatch(r"[PUBC][0-9A-F]{4}", code):
                raise ValueError(f"Invalid diagnostic trouble code: {value!r}")
            normalized.append(code)
        return normalized


class FreezeFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rpm: float = Field(ge=0)
    load_pct: float = Field(ge=0, le=100)
    coolant_c: float
    stft_pct: float
    ltft_pct: float
    map_kpa: float = Field(ge=0)
    speed_kmh: float = Field(ge=0)
    throttle_pct: float = Field(ge=0, le=100)


class LiveData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rpm: float = Field(ge=0)
    coolant_c: float
    intake_c: float
    stft_pct: float
    ltft_pct: float
    maf_gs: float = Field(ge=0)
    map_kpa: float = Field(ge=0)
    timing_deg: float
    o2_up_v: float = Field(ge=0)
    o2_down_v: float = Field(ge=0)


class SnapshotData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle: Vehicle
    codes: Codes
    freeze_frame: FreezeFrame
    live_data: LiveData
    symptoms: str = Field(min_length=1)


def parse_symptoms(text: str) -> dict[str, str | bool]:
    """Deterministic placeholder for a future local-LLM symptom parser."""
    normalized = text.casefold()
    cold = any(term in normalized for term in ("cold", "cold start", "morning"))
    rough = any(term in normalized for term in ("rough", "shake", "shaking", "misfire"))
    flashing = any(
        term in normalized
        for term in ("flashed", "flashing", "blinking", "blink")
    ) and any(term in normalized for term in ("check engine", "cel", "engine light"))
    return {
        "temperature_state": "cold" if cold else "unspecified",
        "idle_quality": "rough" if rough else "unspecified",
        "warning_light": "flashing" if flashing else "steady_or_unspecified",
        "is_misfire_cold": bool(cold and rough),
        "flashing_cel": flashing,
    }


def extract_features(snapshot: SnapshotData) -> pd.DataFrame:
    """Flatten numeric telemetry and categorical symptom features into one row."""
    freeze = snapshot.freeze_frame
    live = snapshot.live_data
    symptoms = parse_symptoms(snapshot.symptoms)
    values: dict[str, Any] = {
        "vehicle_year": snapshot.vehicle.year,
        "vehicle_mileage": snapshot.vehicle.mileage,
        "stored_code_count": len(snapshot.codes.stored),
        "pending_code_count": len(snapshot.codes.pending),
        "freeze_rpm": freeze.rpm,
        "freeze_load_pct": freeze.load_pct,
        "freeze_coolant_c": freeze.coolant_c,
        "freeze_stft_pct": freeze.stft_pct,
        "freeze_ltft_pct": freeze.ltft_pct,
        "freeze_total_fuel_trim_pct": freeze.stft_pct + freeze.ltft_pct,
        "freeze_map_kpa": freeze.map_kpa,
        "freeze_speed_kmh": freeze.speed_kmh,
        "freeze_throttle_pct": freeze.throttle_pct,
        "live_rpm": live.rpm,
        "live_coolant_c": live.coolant_c,
        "live_intake_c": live.intake_c,
        "live_stft_pct": live.stft_pct,
        "live_ltft_pct": live.ltft_pct,
        "live_total_fuel_trim_pct": live.stft_pct + live.ltft_pct,
        "live_maf_gs": live.maf_gs,
        "live_map_kpa": live.map_kpa,
        "live_timing_deg": live.timing_deg,
        "live_o2_up_v": live.o2_up_v,
        "live_o2_down_v": live.o2_down_v,
        **symptoms,
    }
    return pd.DataFrame([values])


def _legacy_model_prediction(features: pd.DataFrame, model_path: Path) -> str | None:
    """Use the existing five-column classifier only when its schema is compatible."""
    if not model_path.is_file():
        return None
    with model_path.open("rb") as model_file:
        bundle = pickle.load(model_file)
    model = bundle.get("model") if isinstance(bundle, dict) else bundle
    expected = bundle.get("feature_columns") if isinstance(bundle, dict) else FEATURE_COLUMNS
    if not hasattr(model, "predict") or expected != FEATURE_COLUMNS:
        return None

    # The legacy classifier was trained on the original telemetry naming scheme.
    legacy = pd.DataFrame(
        [{
            "RPM": features.at[0, "live_rpm"],
            "Engine_Load_pct": features.at[0, "freeze_load_pct"],
            "Short_Term_Fuel_Trim_pct": features.at[0, "live_stft_pct"],
            "Long_Term_Fuel_Trim_pct": features.at[0, "live_ltft_pct"],
            "MAF_g_s": features.at[0, "live_maf_gs"],
        }],
        columns=FEATURE_COLUMNS,
    )
    return str(model.predict(legacy)[0])


def run_diagnosis(
    json_payload: dict[str, Any] | str,
    model_path: str | Path = "auto_diagnost_model.pkl",
) -> str:
    """Validate a submitted snapshot and return a user-facing diagnosis."""
    snapshot = SnapshotData.model_validate_json(json_payload) if isinstance(json_payload, str) else SnapshotData.model_validate(json_payload)
    features = extract_features(snapshot)
    parsed = parse_symptoms(snapshot.symptoms)
    prediction = _legacy_model_prediction(features, Path(model_path))

    if parsed["flashing_cel"]:
        conclusion = "Urgent misfire risk: reduce load and have the vehicle inspected promptly."
    elif "P0301" in snapshot.codes.stored or "P0301" in snapshot.codes.pending:
        conclusion = "Likely Cylinder 1 ignition or fuel fault; swap-test the cylinder 1 coil."
    elif prediction == "maf_sensor_failure":
        conclusion = "Likely failing MAF sensor; compare airflow against RPM and engine load."
    elif prediction == "supercharger_gasket_leak":
        conclusion = "Likely vacuum leak near the supercharger gasket; perform a smoke test."
    elif prediction:
        conclusion = f"Legacy telemetry model classification: {prediction}."
    else:
        conclusion = "No compatible model prediction is available; review the captured evidence manually."

    return (
        f"{conclusion}\n"
        f"Symptoms: {snapshot.symptoms}\n"
        f"Live total fuel trim: {features.at[0, 'live_total_fuel_trim_pct']:.1f}%\n"
        f"Stored DTCs: {', '.join(snapshot.codes.stored) or 'none'}"
    )
