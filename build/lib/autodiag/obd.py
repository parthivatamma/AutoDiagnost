"""OBD readers. The simulator is deliberately the stable offline boundary."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Protocol
from .models import DTC, FreezeFrame, LivePID, Readiness, SnapshotSource, VehicleInfo, VehicleSnapshot

PIDS = ("rpm", "load", "coolant_temp", "intake_temp", "stft", "ltft", "maf", "map", "throttle", "timing_advance", "o2", "fuel_pressure", "voltage")

class OBDReader(Protocol):
    def read_snapshot(self) -> VehicleSnapshot: ...

def _pid(name: str, value: Any) -> LivePID:
    return LivePID(name=name, value=value, available=value is not None)

class SimulatedReader:
    def __init__(self, fixture: str | Path | dict[str, Any]):
        if isinstance(fixture, (str, Path)):
            self.data = json.loads(Path(fixture).read_text())
        else:
            self.data = fixture
    def read_snapshot(self) -> VehicleSnapshot:
        d = dict(self.data)
        d.setdefault("source", SnapshotSource.FIXTURE)
        d["source"] = SnapshotSource(d["source"])
        d["dtcs"] = [x if isinstance(x, DTC) else DTC(**x) if isinstance(x, dict) else DTC(code=x) for x in d.get("dtcs", [])]
        d["live_pids"] = {k: (v if isinstance(v, LivePID) else _pid(k, v) if not isinstance(v, dict) else LivePID(name=k, **v)) for k, v in d.get("live_pids", {}).items()}
        return VehicleSnapshot(**d)

class PythonOBDReader:
    """Best-effort python-OBD adapter; unsupported PIDs remain null."""
    def __init__(self, connection=None, port: str | None = None):
        if connection is None:
            try:
                import obd
                connection = obd.OBD(port)
            except ImportError as e:
                raise RuntimeError("Install autodiagnost[obd] to use a live adapter") from e
        self.connection = connection
    def _query(self, command):
        try:
            response = self.connection.query(command)
            if response is None:
                return None
            is_null = getattr(response, "is_null", False)
            if callable(is_null):
                is_null = is_null()
            if is_null:
                return None
            value = getattr(response, "value", response)
            return getattr(value, "magnitude", value)
        except Exception:
            return None

    def _command(self, obd_module, name):
        return getattr(obd_module.commands, name, None)
    def read_snapshot(self) -> VehicleSnapshot:
        import obd
        command_names = {"rpm": "RPM", "load": "ENGINE_LOAD", "coolant_temp": "COOLANT_TEMP",
                    "intake_temp": "INTAKE_TEMP", "stft": "SHORT_FUEL_TRIM_1",
                    "ltft": "LONG_FUEL_TRIM_1", "maf": "MAF", "map": "INTAKE_PRESSURE",
                    "throttle": "THROTTLE_POS", "timing_advance": "TIMING_ADVANCE",
                    "voltage": "CONTROL_MODULE_VOLTAGE", "fuel_pressure": "FUEL_PRESSURE",
                    "catalyst_temp": "CATALYST_TEMP_B1S1", "distance_since_clear": "DISTANCE_W_MIL"}
        values = {k: self._query(self._command(obd, name)) if self._command(obd, name) else None
                  for k, name in command_names.items()}
        raw = self._query(obd.commands.GET_DTC)
        dtcs = [DTC(code=x[0], description=x[1]) for x in (raw or [])]
        pending_command = self._command(obd, "PENDING_DTC")
        pending = self._query(pending_command) if pending_command else []
        dtcs.extend(DTC(code=x[0], description=x[1], status="pending", pending=True) for x in (pending or []))
        vin = self._query(obd.commands.VIN)
        freeze_command = self._command(obd, "FREEZE_FRAME")
        freeze = self._query(freeze_command) if freeze_command else None
        status_command = self._command(obd, "STATUS")
        status = self._query(status_command) if status_command else None
        return VehicleSnapshot(source=SnapshotSource.ADAPTER, vehicle=VehicleInfo(vin=str(vin) if vin else None),
                               dtcs=dtcs, freeze_frame=FreezeFrame(values=freeze) if isinstance(freeze, dict) else None,
                               readiness=Readiness(complete=getattr(status, "MIL", None)) if status else None,
                               live_pids={k: _pid(k, v) for k, v in values.items()})
