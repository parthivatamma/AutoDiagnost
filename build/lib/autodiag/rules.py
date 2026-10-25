from .dtc import describe
from .models import Severity, VehicleSnapshot

def evaluate(snapshot: VehicleSnapshot) -> dict:
    flags, notes, severity = [], [], Severity.DRIVE_NORMALLY
    vals = {k: p.value for k, p in snapshot.live_pids.items()}
    trims = [vals.get("stft"), vals.get("ltft")]
    if any(isinstance(x, (int, float)) and x > 10 for x in trims): flags.append("positive fuel trims suggest lean operation")
    if any(isinstance(x, (int, float)) and x < -10 for x in trims): flags.append("negative fuel trims suggest rich operation")
    def raise_severity(candidate: Severity) -> None:
        nonlocal severity
        order = list(Severity)
        if order.index(candidate) > order.index(severity):
            severity = candidate

    if isinstance(vals.get("voltage"), (int, float)) and vals["voltage"] < 11.5:
        flags.append("low module voltage"); raise_severity(Severity.LIMIT_DRIVING)
    if isinstance(vals.get("coolant_temp"), (int, float)) and vals["coolant_temp"] > 115:
        notes.append("Overheating detected; stop safely and do not continue driving")
        raise_severity(Severity.DO_NOT_DRIVE)
    codes = {d.code for d in snapshot.dtcs}
    if any(c.startswith("P030") for c in codes):
        flags.append("misfire detected")
        raise_severity(Severity.DRIVE_WITH_CAUTION)
    if any("flash" in symptom.lower() and ("mil" in symptom.lower() or "engine" in symptom.lower())
           for symptom in snapshot.symptoms):
        notes.append("Flashing MIL may damage the catalytic converter; reduce load and stop safely")
        raise_severity(Severity.LIMIT_DRIVING)
    return {"flags": flags, "safety_notes": notes, "severity": severity, "dtcs": [(c, describe(c)) for c in codes]}
