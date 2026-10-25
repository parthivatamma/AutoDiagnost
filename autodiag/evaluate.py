"""Tiny regression runner for fixture-based offline checks."""
from pathlib import Path
from .obd import SimulatedReader
from .reasoning import diagnose

def run(fixtures="fixtures"):
    results = {}
    correct = 0
    for path in sorted(Path(fixtures).glob("*.json")):
        snapshot = SimulatedReader(path).read_snapshot()
        result = diagnose(snapshot)
        expected = snapshot.expected or {}
        top_cause = result.causes[0].title if result.causes else None
        matched = bool(expected.get("cause_contains") and expected["cause_contains"].lower() in (top_cause or "").lower())
        correct += int(matched)
        results[path.name] = {"severity": result.severity.value, "top_cause": top_cause, "expected": expected, "top1_match": matched}
    results["_summary"] = {"fixtures": len(results), "top1_matches": correct}
    return results
