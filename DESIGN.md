# AutoDiagnost: Engine Diagnostic Assistant

Status: Final MVP design
Author: rtamma
Date: 2026-09-16

## 1. Product Goal

AutoDiagnost turns an OBD-II snapshot into a grounded diagnostic plan. It combines trouble codes, freeze-frame data, live sensor values, symptoms, and service knowledge to produce ranked probable causes, the next test that best separates them, and the evidence behind each conclusion.

The product is decision support for a driver or technician, not a substitute for a qualified technician. Safety warnings and uncertainty are mandatory.

## 2. MVP Scope

The long-term MVP surface covers engine and emissions-related powertrain faults (generic P0xxx codes). The first end-to-end vertical slice is one gasoline vehicle and the misfire family, especially P030x codes. Misfire is the fastest useful demonstration because it can be diagnosed with DTCs, freeze-frame values, RPM/load, fuel trims, and technician notes.

### First vertical slice

- Read or load DTCs, freeze-frame data, readiness monitors, VIN, and relevant live PIDs.
- Normalize the input into a stable JSON snapshot.
- Apply deterministic checks for obvious and safety-critical conditions.
- Retrieve relevant troubleshooting passages.
- Return three ranked causes, confidence, evidence, one or more confirming tests, and severity.
- Run from a CLI against a real adapter or a saved fixture.

### Included in the broader MVP

- Generic workflows for lean conditions, catalyst efficiency, EVAP leaks, thermostat faults, and MAF/MAP plausibility.
- Optional audio features and image/video frames as additional evidence.
- A local searchable knowledge base with page-level citations.
- A Python API boundary that can later back a web UI.

### Explicit non-goals

- Bidirectional controls, actuator tests, module programming, or autonomous repair actions.
- Manufacturer-specific enhanced PIDs (Mode 22) and permanent DTCs (Mode 0A).
- Full OEM coverage, CAN reverse engineering, repair-cost estimation, or mobile/web UI work in the first weekend.
- Real-time streaming dashboards. One snapshot per diagnosis is sufficient.

## 3. Users and Primary Flow

The users are DIY owners with an ELM327-compatible adapter and technicians who want a faster first diagnostic pass.

1. Connect an adapter or select a saved fixture.
2. Run `autodiag scan` to capture and normalize the vehicle snapshot.
3. Add symptoms, technician notes, and optional media.
4. Run `autodiag diagnose`.
5. Review ranked causes, cited evidence, severity, and the cheapest useful confirming test.
6. Perform the test, add its result as a new symptom, and rerun.

## 4. User-Visible Output

Every diagnosis returns structured data and a readable CLI report:

```json
{
  "causes": [
    {
      "rank": 1,
      "title": "Ignition coil weak on cylinder 1",
      "probability": 0.74,
      "reasoning": "P0301 and a cylinder-specific misfire pattern point to...",
      "evidence": [
        { "kind": "obd", "detail": "P0301", "source": "snapshot" },
        { "kind": "manual", "detail": "Ignition diagnostics", "source": "c3" }
      ]
    }
  ],
  "severity": "drive_with_caution",
  "next_tests": [
    {
      "order": 1,
      "name": "Swap the cylinder 1 coil with cylinder 2",
      "expected_if_faulty": "The misfire moves to cylinder 2",
      "expected_if_ok": "The misfire remains on cylinder 1"
    }
  ],
  "safety_notes": []
}
```

The complete `Diagnosis` model contains `summary`, `severity`, ranked `causes`, `next_tests`, `missing_information`, and `safety_notes`. Probabilities are renormalized after validation and should sum approximately to 1.

Severity values are:

- `drive_normally`
- `drive_with_caution`
- `limit_driving`
- `do_not_drive`

Overheating, suspected oil-pressure loss, a flashing MIL with severe running problems, or other red-flag patterns must be surfaced before ordinary advice.

## 5. Architecture

```
             ELM327 adapter or JSON fixture
                         |
                         v
              obd/ -> VehicleSnapshot
                 /                 \\
                v                   v
       deterministic rules     knowledge/
       and derived flags      ingest -> SQLite FTS5
                \\                   /
                 v                 v
              reasoning/ -> Diagnosis
                         |
                         v
                   CLI report + JSON
```

All boundaries communicate through Pydantic models so each layer can be tested or replaced independently.

### 5.1 OBD layer

`OBDReader` has two implementations:

- `PythonOBDReader` wraps python-OBD and queries Mode 03 stored DTCs, Mode 07 pending DTCs, Mode 01 live PIDs, Mode 02 freeze-frame data, Mode 01 readiness bits, and Mode 09 VIN.
- `SimulatedReader` loads the same fields from a JSON fixture. Fixtures are also regression cases, beginning with P0301 and P0171.

The curated PID set includes RPM, load, coolant and intake temperature, short- and long-term fuel trims, MAF, MAP, throttle, timing advance, O2 values, fuel pressure, module voltage, catalyst temperature, and distance since clear. Unsupported or unavailable PIDs are recorded as null and skipped, never treated as fatal.

`VehicleSnapshot` contains vehicle information, DTCs and status, freeze-frame values, live PIDs, readiness, symptoms, and a `source` value. A small generic SAE DTC table supplies descriptions when the adapter does not.

### 5.2 Deterministic rules

Rules run before the LLM and provide derived flags such as:

- fuel trims beyond plus or minus 10 percent
- low battery voltage
- coolant outside expected warm-up range
- stuck O2 readings
- implausible MAP or MAF for the current RPM
- flashing MIL or severe misfire indicators

Safety-critical rules can raise severity without waiting for model output.

## 6. Knowledge and Retrieval

The default knowledge base is a local SQLite database at `~/.autodiag/kb.sqlite`. It contains `documents`, `chunks`, and an FTS5 index over chunk text. SQLite FTS5 is deliberately used for the first MVP: it is offline, requires no service, and performs well for exact DTCs and part names. The retriever interface leaves room for hybrid embeddings later.

`autodiag ingest PATH...` supports PDF, Markdown, and text. PDF pages remain separate for citations; Markdown and text split on headings. Chunks target about 800 tokens with 100 tokens of overlap and retain document title, page, content hash, and stable chunk ID. Re-ingesting the same content is a no-op.

The deterministic query builder combines DTCs and descriptions, vehicle metadata, symptoms, and abnormal PID names. Retrieval runs DTC, symptom, and combined FTS queries, merges them with reciprocal rank fusion, and returns the top 12 chunks. Each chunk receives a handle such as `c1` that the model must use when citing manual evidence.

Seed knowledge is generic, hand-written guidance for misfire isolation, lean conditions, catalyst efficiency, EVAP leaks, thermostat faults, and MAF/MAP plausibility. Manufacturer material remains local and its licensing is the user's responsibility.

## 7. Reasoning Layer

The first implementation makes one structured LLM call. The human performs the recommended test, creating the natural diagnostic loop without the cost and unpredictability of an agent loop.

Context is assembled in this order for stable caching:

1. Diagnostic method and safety instructions.
2. Retrieved chunks with citation handles, titles, and pages.
3. Compact snapshot JSON and code-derived flags.
4. Free-text symptoms and test results.
5. Optional audio feature summary and image content blocks.

The prompt requires evidence before conclusions, tests that split the candidate set, explicit contradictions, no invented manual content, and a clear distinction between OBD evidence, manual evidence, symptoms, and general knowledge.

Post-processing verifies that every citation handle was supplied, flags unknown handles, removes invalid cause references from tests, and renormalizes probabilities. Refusals and API errors become clear CLI errors; token-limit failures may retry once with a larger budget.

## 8. Optional Media

Audio is converted to text features because the model interface does not accept raw audio. The MVP extracts duration, RMS level, dominant frequencies, and repeating impulse rate from WAV files; other formats require ffmpeg. RPM provides context for comparing half-crank and crank-frequency patterns.

Images can represent spark plugs, leaks, or dashboard indicators. Video is sampled into a small number of frames with ffmpeg. Media is optional and never changes the no-media pipeline.

## 9. CLI and Repository Layout

| Command          | Purpose                                                  |
| ---------------- | -------------------------------------------------------- |
| `scan`           | Read the adapter or `--fixture` and save a snapshot JSON |
| `ingest PATH...` | Add manuals and guides to the local knowledge base       |
| `search QUERY`   | Inspect retrieval results                                |
| `diagnose`       | Run diagnosis from a snapshot or fixture and write JSON  |
| `demo`           | Run the bundled misfire case with seed knowledge         |

```text
AutoDiagnost/
  DESIGN.md
  README.md
  pyproject.toml
  autodiag/
    models.py
    cli.py
    obd/reader.py
    obd/dtc_db.py
    knowledge/ingest.py
    knowledge/store.py
    knowledge/retriever.py
    reasoning/prompts.py
    reasoning/diagnose.py
    reasoning/validate.py
    media/audio.py
    media/video.py
  knowledge/seed/*.md
  fixtures/*.json
  tests/
```

The current repository scripts can serve as the initial implementation surface while this package layout is introduced incrementally.

## 10. Weekend Implementation Plan

### Saturday morning: data collection

- Connect to an adapter or use a fixture.
- Capture VIN, active and pending DTCs, freeze-frame data, RPM, coolant, load, and fuel trims.
- Save and validate one normalized payload, for example a P0301 with rough idle and elevated short-term fuel trim.

**Exit criterion:** one command produces a valid `VehicleSnapshot` from live or simulated input.

### Saturday afternoon: knowledge base

- Start with 5 to 20 documents or seed notes.
- Ingest, chunk, index, and preserve source metadata.
- Test queries such as `P0301 rough idle` and `misfire under load cylinder 1`.

**Exit criterion:** retrieval returns relevant passages with stable citation handles.

### Saturday evening: diagnosis pipeline

- Accept a snapshot and symptoms.
- Run rules, build a query, retrieve the top passages, call the LLM, validate the schema, and render JSON plus a CLI report.
- Require ranked hypotheses, a confirming test, uncertainty, and safety notes.

**Exit criterion:** the misfire demo produces three ranked hypotheses and cites only supplied evidence.

### Sunday: guardrails and evaluation

- Add the severity classifier and red-flag rules.
- Create ten cases: four real captures when available and six synthetic cases.
- Score top-1 and top-3 cause accuracy, first-test usefulness, citation validity, and unsafe recommendations.

**Exit criterion:** a repeatable demo runs from a saved payload and reports its evaluation results.

## 11. Evaluation and Acceptance Criteria

Each fixture has an `expected` block containing the true cause and the test that confirms it. Model or prompt changes are accepted only when they do not regress the evaluation set.

The initial acceptance bar is:

- ingest one real or saved OBD payload
- retrieve relevant troubleshooting passages
- produce three ranked hypotheses
- recommend a reasonable next test
- show evidence with resolvable citations
- avoid unsafe advice on red-flag cases
- complete the offline pipeline in under one minute, excluding the LLM call

## 12. Privacy, Security, and Risks

- VIN is sensitive vehicle information. Reports remain local, and `--no-vin` redacts it from the LLM prompt.
- Only the assembled context is sent to the model API; manuals remain local.
- API credentials come from environment variables or the supported CLI login, never from source files.
- Cheap adapters may drop PIDs or time out. Null-tolerant parsing and a slow mode mitigate this.
- BM25 may miss paraphrases. The first upgrade, if evaluation shows recall gaps, is hybrid retrieval with embeddings and vehicle filtering.
- Audio features are coarse and must remain weak evidence.
- A single high-capability model call can be expensive, so retrieved context and system instructions should be cache-friendly.

## 13. Milestones

1. **M1: weekend MVP.** Simulator, adapter path, SQLite FTS5 knowledge base, misfire diagnosis, CLI, seed knowledge, fixtures, rules, and tests.
2. **M2: diagnostic breadth.** Additional generic fault families, hybrid retrieval, vehicle-scoped filtering, 20 or more evaluation fixtures, and iterative sessions.
3. **M3: advanced coverage.** Mode 22 tables, permanent DTCs, drive-cycle capture for intermittent faults, and a user interface.

## 14. Decisions Log

- Python is the implementation language because python-OBD is mature and NumPy supports the optional audio features.
- SQLite FTS5 is preferred to a vector database for the first release because it is local, deterministic, and zero-setup.
- CLI first keeps the core workflow testable and makes a web UI optional.
- Deterministic query construction is preferred to LLM query rewriting.
- A single structured call is preferred to an agent loop; human test results provide the iteration.
- The first fault family is misfire, while the data model and interfaces are broad enough for the planned generic P0xxx workflows.
