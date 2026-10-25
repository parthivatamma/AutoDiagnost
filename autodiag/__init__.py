"""Core package for the AutoDiagnost diagnostic assistant."""

from .models import (
    DTC,
    FreezeFrame,
    LivePID,
    Readiness,
    SnapshotSource,
    VehicleInfo,
    VehicleSnapshot,
    Severity, Evidence, Cause, NextTest, Diagnosis,
)
from .ingestion import (
    Codes as StructuredCodes,
    FreezeFrame as StructuredFreezeFrame,
    LiveData,
    SnapshotData,
    Vehicle as StructuredVehicle,
    extract_features,
    parse_symptoms,
    run_diagnosis,
)
from .obd import OBDReader, SimulatedReader, PythonOBDReader

__all__ = [
    "DTC",
    "FreezeFrame",
    "LivePID",
    "Readiness",
    "SnapshotSource",
    "VehicleInfo",
    "VehicleSnapshot",
    "StructuredVehicle",
    "StructuredCodes",
    "StructuredFreezeFrame",
    "LiveData",
    "SnapshotData",
    "extract_features",
    "parse_symptoms",
    "run_diagnosis",
    "Severity", "Evidence", "Cause", "NextTest", "Diagnosis",
    "OBDReader", "SimulatedReader", "PythonOBDReader",
]
