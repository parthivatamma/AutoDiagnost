from typing import Protocol
from .dtc import describe
from .models import Cause, Diagnosis, Evidence, NextTest, Severity, VehicleSnapshot
from .rules import evaluate

class LLMProvider(Protocol):
    def diagnose(self, prompt: str) -> dict: ...

def _renormalize(causes):
    total = sum(max(0, c.probability) for c in causes)
    if not total: return causes
    return [c.model_copy(update={"probability": c.probability / total}) for c in causes]

def diagnose(snapshot: VehicleSnapshot, knowledge=None, provider: LLMProvider | None = None) -> Diagnosis:
    flags = evaluate(snapshot)
    docs = knowledge.search(" ".join([d.code + " " + describe(d.code) for d in snapshot.dtcs] + snapshot.symptoms)) if knowledge else []
    if provider:
        raw = provider.diagnose(str({"snapshot": snapshot.redacted().to_json_dict(), "flags": flags, "citations": docs}))
        try:
            result = Diagnosis.model_validate(raw)
            valid = set(x["handle"] for x in docs)
            result = result.model_copy(update={"citations": {k:v for k,v in result.citations.items() if k in valid}})
            return result.model_copy(update={"causes": _renormalize(result.causes)})
        except Exception:
            pass
    codes = {d.code for d in snapshot.dtcs}
    causes = []
    if any(c.startswith("P030") for c in codes):
        cyl = next((str(int(c[3:])) for c in codes if c.startswith("P030") and c != "P0300"), "")
        causes.append(Cause(rank=1, title=f"Ignition or fuel fault on cylinder {cyl}" if cyl else "Ignition or fuel fault", probability=.7, reasoning="Cylinder-specific misfire code is direct OBD evidence.", evidence=[Evidence(kind="obd", detail=c, source="snapshot") for c in codes]))
        causes.append(Cause(rank=2, title="Vacuum leak or injector issue", probability=.3, reasoning="A lean condition can cause intermittent misfire.", evidence=[Evidence(kind="rule", detail=x) for x in flags["flags"]]))
        tests = [NextTest(order=1, name="Swap the suspect ignition coil with a neighboring cylinder", expected_if_faulty="Misfire moves", expected_if_ok="Misfire remains")]
    elif "P0171" in codes:
        causes = [Cause(rank=1, title="Unmetered air or fuel delivery restriction", probability=1, reasoning="Lean-system DTC and fuel-trim evidence.", evidence=[Evidence(kind="obd", detail="P0171")])]
        tests = [NextTest(order=1, name="Inspect intake for leaks", expected_if_faulty="Trim improves after repair", expected_if_ok="No change")]
    else:
        causes = [Cause(rank=1, title=describe(next(iter(codes), "P0000")), probability=1, reasoning="No specialized offline rule matched.", evidence=[])]
        tests = []
    return Diagnosis(summary="Offline deterministic assessment; confirm before repairing.", severity=flags["severity"], causes=_renormalize(causes), next_tests=tests, safety_notes=flags["safety_notes"], citations={d["handle"]: d["title"] for d in docs})
