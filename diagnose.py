import argparse
import pickle
import time
from pathlib import Path
from typing import Any

import pandas as pd

from obd_telemetry import FEATURE_COLUMNS, open_connection, read_telemetry

DEFAULT_MODEL = Path("auto_diagnost_model.pkl")
DEFAULT_INTERVAL = 2.0
DIAGNOSIS_MESSAGES = {
    "normal": "No modeled fault detected in the current telemetry.",
    "maf_sensor_failure": (
        "Likely failing MAF sensor: airflow reporting is inconsistent with the "
        "engine operating conditions."
    ),
    "supercharger_gasket_leak": (
        "Likely supercharger gasket vacuum leak: fuel trims suggest unmetered air "
        "after the MAF sensor."
    ),
}


def load_model(model_path: Path) -> tuple[Any, list[str]]:
    if not model_path.is_file():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    with model_path.open("rb") as model_file:
        bundle = pickle.load(model_file)

    if isinstance(bundle, dict):
        model = bundle.get("model")
        feature_columns = bundle.get("feature_columns")
    else:
        model = bundle
        feature_columns = FEATURE_COLUMNS

    if model is None or not hasattr(model, "predict"):
        raise ValueError("Model file does not contain a usable classifier.")
    if feature_columns != FEATURE_COLUMNS:
        raise ValueError(
            "Model feature schema does not match live telemetry: "
            f"expected {FEATURE_COLUMNS}, got {feature_columns}."
        )
    return model, feature_columns


def diagnose_sample(model: Any, telemetry_frame: pd.DataFrame) -> str:
    missing = [column for column in FEATURE_COLUMNS if column not in telemetry_frame]
    if missing:
        raise ValueError(f"Telemetry is missing model features: {', '.join(missing)}")

    prediction = str(model.predict(telemetry_frame[FEATURE_COLUMNS])[0])
    return DIAGNOSIS_MESSAGES.get(
        prediction,
        f"Classifier returned an unknown diagnosis: {prediction}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AutoDiagnost live OBD-II inference engine."
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--port", help="Serial port, such as /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, help="Optional ELM327 baud rate.")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help=f"Seconds between readings (default: {DEFAULT_INTERVAL}).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Read and classify one sample, then exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.interval <= 0:
        raise ValueError("--interval must be greater than zero.")

    model, _ = load_model(args.model)
    connection = open_connection(args.port, args.baudrate)
    try:
        while True:
            telemetry = read_telemetry(connection)
            frame = telemetry.to_frame()
            print(frame.to_string(index=False))
            print(f"Diagnosis: {diagnose_sample(model, frame)}\n")
            if args.once:
                break
            time.sleep(args.interval)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
