import argparse
import random
import threading
from pathlib import Path
from typing import Callable

from diagnose import diagnose_sample, load_model
from obd_telemetry import OBDTelemetry

STATE_NAMES = {
    0: "Healthy",
    1: "Vacuum Leak",
    2: "Failing MAF",
}


class MockOBD:
    """Generate deterministic-shaped OBD-II telemetry for three fault states."""

    def __init__(self, state: int = 0, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._state = 0
        self.set_state(state)

    @property
    def state(self) -> int:
        return self._state

    def set_state(self, state: int) -> None:
        if state not in STATE_NAMES:
            raise ValueError("State must be 0 (healthy), 1 (vacuum leak), or 2 (failing MAF).")
        self._state = state

    def read(self) -> OBDTelemetry:
        rpm = self._rng.uniform(800, 5500)
        load = self._rng.uniform(15, 95)
        expected_maf = 0.00018 * rpm * load * self._rng.uniform(0.82, 0.96)

        if self.state == 0:
            maf = expected_maf + self._rng.gauss(0, 0.8)
            stft = self._rng.gauss(0, 2)
            ltft = self._rng.gauss(0, 1.5)
        elif self.state == 1:
            maf = expected_maf + self._rng.gauss(0, 1)
            low_load_factor = max(0.0, min(1.0, (60 - load) / 45))
            stft = self._rng.gauss(8, 2.5) + low_load_factor * self._rng.gauss(8, 2)
            ltft = self._rng.gauss(14, 3) + low_load_factor * self._rng.gauss(5, 1.5)
        else:
            maf = expected_maf * self._rng.uniform(0.55, 0.75) + self._rng.gauss(0, 3)
            stft = self._rng.gauss(12, 4)
            ltft = self._rng.gauss(8, 3)

        return OBDTelemetry(
            rpm=round(rpm, 1),
            engine_load_pct=round(load, 1),
            short_term_fuel_trim_pct=round(stft, 1),
            long_term_fuel_trim_pct=round(ltft, 1),
            maf_g_s=round(max(maf, 0.1), 2),
        )


def _keyboard_listener(mock_obd: MockOBD, stop: threading.Event) -> None:
    print("Commands: 0=Healthy, 1=Vacuum Leak, 2=Failing MAF, q=Quit")
    while not stop.is_set():
        try:
            command = input("state> ").strip().lower()
        except EOFError:
            return
        if command == "q":
            stop.set()
            return
        try:
            mock_obd.set_state(int(command))
            print(f"Switched to State {mock_obd.state}: {STATE_NAMES[mock_obd.state]}")
        except (TypeError, ValueError):
            print("Enter 0, 1, 2, or q.")


def run_simulation(
    mock_obd: MockOBD,
    model_path: str,
    interval: float = 1.0,
    samples: int | None = None,
    interactive: bool = True,
    output: Callable[[str], None] = print,
) -> None:
    if interval <= 0:
        raise ValueError("Interval must be greater than zero.")
    model, _ = load_model(Path(model_path))
    stop = threading.Event()
    listener = None
    if interactive and samples is None:
        listener = threading.Thread(
            target=_keyboard_listener, args=(mock_obd, stop), daemon=True
        )
        listener.start()

    count = 0
    try:
        while not stop.is_set() and (samples is None or count < samples):
            telemetry = mock_obd.read()
            frame = telemetry.to_frame()
            output(f"State {mock_obd.state} ({STATE_NAMES[mock_obd.state]})")
            output(frame.to_string(index=False))
            output(f"Diagnosis: {diagnose_sample(model, frame)}")
            count += 1
            if samples is None or count < samples:
                stop.wait(interval)
    except KeyboardInterrupt:
        output("Simulation stopped.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AutoDiagnost dummy OBD-II stream.")
    parser.add_argument("--state", type=int, choices=STATE_NAMES, default=0)
    parser.add_argument("--model", default="auto_diagnost_model.pkl")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--samples", type=int, help="Generate a finite number of samples.")
    parser.add_argument("--no-input", action="store_true", help="Disable keyboard state changes.")
    parser.add_argument("--seed", type=int, help="Seed the simulated readings.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples is not None and args.samples <= 0:
        raise ValueError("--samples must be greater than zero.")
    run_simulation(
        MockOBD(args.state, args.seed),
        args.model,
        args.interval,
        args.samples,
        interactive=not args.no_input,
    )


if __name__ == "__main__":
    main()
