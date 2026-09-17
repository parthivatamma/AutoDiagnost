import argparse
from dataclasses import dataclass
from typing import Any

import pandas as pd

FEATURE_COLUMNS = [
    "RPM",
    "Engine_Load_pct",
    "Short_Term_Fuel_Trim_pct",
    "Long_Term_Fuel_Trim_pct",
    "MAF_g_s",
]


@dataclass
class OBDTelemetry:
    rpm: float
    engine_load_pct: float
    short_term_fuel_trim_pct: float
    long_term_fuel_trim_pct: float
    maf_g_s: float

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "RPM": self.rpm,
                    "Engine_Load_pct": self.engine_load_pct,
                    "Short_Term_Fuel_Trim_pct": self.short_term_fuel_trim_pct,
                    "Long_Term_Fuel_Trim_pct": self.long_term_fuel_trim_pct,
                    "MAF_g_s": self.maf_g_s,
                }
            ],
            columns=FEATURE_COLUMNS,
        )


def _numeric_value(response: Any, command_name: str) -> float:
    is_null = getattr(response, "is_null", False)
    if callable(is_null):
        is_null = is_null()
    if response is None or is_null:
        raise RuntimeError(f"OBD command {command_name} returned no data.")

    value = getattr(response, "value", response)
    magnitude = getattr(value, "magnitude", value)
    try:
        return float(magnitude)
    except (TypeError, ValueError) as error:
        raise RuntimeError(
            f"OBD command {command_name} returned a non-numeric value: {value!r}"
        ) from error


def read_telemetry(connection: Any) -> OBDTelemetry:
    """Read one complete telemetry sample from an open python-obd connection."""
    try:
        from obd import commands
    except ImportError as error:
        raise RuntimeError(
            "python-obd is required for live telemetry. Install it with "
            "`python3 -m pip install obd`."
        ) from error

    command_map = {
        "RPM": commands.RPM,
        "Engine_Load_pct": commands.ENGINE_LOAD,
        "Short_Term_Fuel_Trim_pct": commands.SHORT_TERM_FUEL_TRIM_BANK_1,
        "Long_Term_Fuel_Trim_pct": commands.LONG_TERM_FUEL_TRIM_BANK_1,
        "MAF_g_s": commands.MAF,
    }
    values = {}
    for column, command in command_map.items():
        response = connection.query(command)
        values[column] = _numeric_value(response, column)

    return OBDTelemetry(
        rpm=values["RPM"],
        engine_load_pct=values["Engine_Load_pct"],
        short_term_fuel_trim_pct=values["Short_Term_Fuel_Trim_pct"],
        long_term_fuel_trim_pct=values["Long_Term_Fuel_Trim_pct"],
        maf_g_s=values["MAF_g_s"],
    )


def open_connection(port: str | None = None, baudrate: int | None = None) -> Any:
    try:
        import obd
    except ImportError as error:
        raise RuntimeError(
            "python-obd is required for live telemetry. Install it with "
            "`python3 -m pip install obd`."
        ) from error

    connection = obd.OBD(portstr=port, baudrate=baudrate, timeout=5)
    if not connection.is_connected():
        connection.close()
        raise ConnectionError(
            "Unable to connect to the ELM327 adapter. Check the adapter, vehicle "
            "ignition, and serial port."
        )
    return connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read one live AutoDiagnost OBD-II telemetry sample."
    )
    parser.add_argument("--port", help="Serial port, such as /dev/ttyUSB0.")
    parser.add_argument("--baudrate", type=int, help="Optional ELM327 baud rate.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    connection = open_connection(args.port, args.baudrate)
    try:
        print(read_telemetry(connection).to_frame().to_string(index=False))
    finally:
        connection.close()


if __name__ == "__main__":
    main()
