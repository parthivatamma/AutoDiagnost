# AUTODIAGNOST // OFFLINE VEHICLE INFERENCE

> Offline-first OBD-II diagnostic decision support that ingests ECU snapshots or live ELM327 telemetry, routes evidence through deterministic safety rules and SQLite FTS5 retrieval, and optionally classifies legacy five-feature streams with a 200-tree scikit-learn model on Python 3.10+ workstations.

[![Design: Industrial Monochrome](https://img.shields.io/badge/DESIGN-INDUSTRIAL_MONOCHROME-black?style=flat-square)](DESIGN.md)
[![Protocol: OBD-II%20%2B%20ELM327](https://img.shields.io/badge/PROTOCOL-OBD--II%20%2B%20ELM327-black?style=flat-square)](autodiag/obd.py)
[![Stack: Python%20%2B%20Pydantic](https://img.shields.io/badge/STACK-PYTHON%20%2B%20PYDANTIC-black?style=flat-square)](pyproject.toml)

## Overview

**AutoDiagnost is not just an OBD-II reader; it is a local diagnostic evidence pipeline.** It polls an ELM327 adapter over the OBD-II command layer, or replays a JSON fixture through the same `VehicleSnapshot` boundary. The pipeline validates the payload, extracts DTCs, freeze-frame data, live PIDs, readiness, and symptoms, then routes the evidence through severity rules, an optional SQLite FTS5 knowledge layer, and an optional `LLMProvider`. If an external provider is absent or returns an invalid schema, the system locks onto deterministic offline reasoning instead of fabricating a confident answer.

The design prioritizes bounded failure over theatrical certainty. Pydantic rejects unknown or malformed snapshot fields, VINs are redacted before external prompts, SQLite chunks technical Markdown with SHA-256 content hashes, and every diagnosis can carry ranked causes, evidence, next tests, citations, and safety notes. A parallel legacy path preserves the original five-column telemetry classifier: a 200-estimator `RandomForestClassifier` consumes RPM, engine load, fuel trims, and MAF values for live or simulated inference.

## Architecture & State/Routing Matrix

The primary bottleneck is not model arithmetic; it is unreliable vehicle I/O and incomplete PID support. A live `python-obd` query can block for up to the adapter’s `timeout=5` seconds, while individual ECUs may return null for unsupported commands. AutoDiagnost isolates that boundary, preserves null availability in the snapshot, and routes the surviving evidence through deterministic rules before any optional model call. Knowledge retrieval is local SQLite FTS5 with a default `LIMIT 12`, so diagnosis remains usable without a network or cloud dependency.

| Stage | Input / Mechanism | Routing Decision | Output / State |
|---|---|---|---|
| Capture | ELM327 via `python-obd`, or `SimulatedReader` fixture replay | Query supported PIDs; retain unsupported values as `null` | `ONLINE` snapshot from `adapter`, `fixture`, or `simulator` |
| Validate | Pydantic `VehicleSnapshot` with `extra="forbid"` and typed DTC/PID models | Reject malformed fields; normalize DTC codes to uppercase | `ACCEPTED` or explicit validation error |
| Safety gate | `rules.evaluate()` checks fuel trims, voltage, coolant temperature, misfire DTCs, and flashing MIL symptoms | Raise severity monotonically from `DRIVE_NORMALLY` through `DO_NOT_DRIVE` | `DRIVE_NORMALLY`, `DRIVE_WITH_CAUTION`, `LIMIT_DRIVING`, or `DO_NOT_DRIVE` |
| Evidence retrieval | SQLite tables plus FTS5 `chunks_fts`; SHA-256 detects unchanged documents | Search DTC descriptions and symptoms; cap results at 12 chunks | `EVIDENCE_READY` with citation handles |
| Reasoning | Optional `LLMProvider` receives a VIN-redacted snapshot, flags, and citations | Accept only schema-valid `Diagnosis`; otherwise use offline rules | `PROVIDER` or `FALLBACK` |
| Deterministic fallback | P030x and P0171 rules, cause renormalization, next-test generation | Avoid unsupported claims when no specialized rule matches | `DIAGNOSED` or `UNKNOWN` |
| Termination | JSON serialization or terminal output; live adapter closes in `finally` | Persist snapshot/result only when an output path is supplied | `CLOSED` or `SYS.HALT` on explicit error |

## Core Engineering Features

- **Validated Boundaries:** `SnapshotData` and `VehicleSnapshot` enforce typed ranges, reject unexpected fields, normalize DTCs, and preserve `available=False` semantics for unsupported live PIDs instead of silently substituting values.
- **Safety-First Routing:** `rules.evaluate()` escalates severity for low module voltage below `11.5 V`, coolant above `115 °C`, `P030x` misfires, and flashing MIL symptoms; severity only moves toward restriction, never toward a safer state.
- **Evidence Retrieval:** `KnowledgeStore` chunks Markdown by heading, hashes content with SHA-256, stores it in SQLite, and queries the FTS5 virtual table with a default 12-result cap. Re-ingesting unchanged material returns zero new chunks.
- **Dual Inference Engines:** The structured path ranks causes and next tests with Pydantic `Diagnosis` models; the legacy path uses a reproducible `random_state=42` Random Forest with a stratified 80/20 split and validates the exact five-column feature schema before prediction.

## Tech Stack

**Snapshot and Reasoning Core**

- `Python >=3.10` for the CLI, adapters, fixture runner, and standalone scripts.
- `Pydantic >=2.0` for strict input boundaries, typed diagnosis output, field validators, and VIN-safe redaction.
- `pandas >=2.0` for model-ready feature frames and telemetry serialization.
- `sqlite3` plus SQLite `FTS5` for zero-service local knowledge retrieval.

**Vehicle / Edge Adapter**

- `python-obd >=0.7` for optional ELM327 serial communication over the OBD-II protocol.
- `ELM327` hardware for the physical edge connection to the vehicle ECU.
- `SimulatedReader` and JSON fixtures for deterministic offline replay without a vehicle.
- `obd_telemetry.py` for five-PID live reads: RPM, engine load, STFT, LTFT, and MAF.

**Legacy ML Path**

- `scikit-learn >=1.4` for the 200-estimator `RandomForestClassifier`.
- `joblib >=1.3` and Python `pickle` bundle model artifacts with the exact feature schema.
- `numpy >=1.24` and `pandas` for the 1,800-row synthetic dataset: 600 samples each across normal, MAF failure, and supercharger gasket leak classes.

**Verification**

- `pytest >=8.0` for fixture scans, validation, FTS5 idempotency, symptom parsing, and safety-rule regression coverage.

## Installation & Boot Sequence

### 1. The Workstation Node (Python 3.10+)

Initialize the local package and its console entry point.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .

# Optional: enable live ELM327 access and the legacy ML training path.
python3 -m pip install -e '.[obd,ml,dev]'
```

### 2. The Knowledge Node (SQLite FTS5)

Load the local diagnostic corpus into the default `~/.autodiag/kb.sqlite` store.

```bash
autodiag ingest knowledge/*.md

# Verify retrieval through the FTS5 index.
autodiag search "P0301 coil"
```

### 3. The Offline Simulation Node (No Vehicle Required)

Ignite the deterministic fixture path before attaching hardware.

```bash
# Run the built-in P0301 demonstration.
autodiag demo

# Scan a fixture into a validated VehicleSnapshot.
autodiag scan --fixture fixtures/p0301.json

# Produce a ranked diagnosis with safety notes and next tests.
autodiag diagnose --fixture fixtures/p0301.json

# Evaluate every JSON fixture and print top-cause matches.
autodiag evaluate --fixtures fixtures
```

### 4. The Legacy Classifier Node (Optional)

Replay the original five-feature model against a controllable simulated OBD stream.

```bash
# Generate finite, reproducible output; 1.0 second between samples.
python3 mock_obd.py --state 0 --samples 5 --no-input --seed 42

# Train the 200-tree model from the checked-in CSV and write the pickle bundle.
python3 train_model.py
```

### 5. The Vehicle Edge Node (ELM327)

Engage the live adapter only with the vehicle ignition in the required state.

```bash
# Read one complete five-PID sample; auto-detect the serial adapter.
python3 obd_telemetry.py

# Run continuous inference with a 2.0 second polling interval.
python3 diagnose.py --interval 2.0

# Pin a serial port and perform one read/classification cycle.
python3 diagnose.py --port /dev/ttyUSB0 --once
```

Navigate to the terminal output and confirm a serialized snapshot or `Diagnosis:` line; when the adapter is unavailable, use the fixture commands to verify the system without vehicle I/O.

