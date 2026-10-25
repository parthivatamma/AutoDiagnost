import argparse, json
from pathlib import Path
from .obd import SimulatedReader, PythonOBDReader
from .knowledge import KnowledgeStore
from .reasoning import diagnose
from .evaluate import run as evaluate_fixtures
from .models import VehicleSnapshot

def main(argv=None):
    p = argparse.ArgumentParser(prog="autodiag")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan"); s.add_argument("--fixture"); s.add_argument("--port"); s.add_argument("--output", type=Path)
    i = sub.add_parser("ingest"); i.add_argument("paths", nargs="+"); i.add_argument("--db", default="~/.autodiag/kb.sqlite")
    q = sub.add_parser("search"); q.add_argument("query"); q.add_argument("--db", default="~/.autodiag/kb.sqlite")
    d = sub.add_parser("diagnose"); d.add_argument("--fixture"); d.add_argument("--snapshot", type=Path); d.add_argument("--db", default="~/.autodiag/kb.sqlite"); d.add_argument("--output", type=Path); d.add_argument("--no-vin", action="store_true")
    sub.add_parser("demo")
    e = sub.add_parser("evaluate"); e.add_argument("--fixtures", default="fixtures")
    a = p.parse_args(argv)
    if a.cmd == "scan":
        reader = SimulatedReader(a.fixture) if a.fixture else PythonOBDReader(port=a.port)
        snapshot = reader.read_snapshot()
        if a.output:
            snapshot.write_json(a.output)
        else:
            print(json.dumps(snapshot.to_json_dict(), indent=2))
    elif a.cmd == "ingest": print(f"ingested {KnowledgeStore(a.db).ingest(a.paths)} chunks")
    elif a.cmd == "search":
        for x in KnowledgeStore(a.db).search(a.query): print(f"{x['handle']} {x['title']} p{x['page']}: {x['text'][:300]}")
    elif a.cmd == "diagnose":
        if bool(a.fixture) == bool(a.snapshot):
            d.error("provide exactly one of --fixture or --snapshot")
        snapshot = SimulatedReader(a.fixture).read_snapshot() if a.fixture else VehicleSnapshot.from_json_file(str(a.snapshot))
        if a.no_vin:
            snapshot = snapshot.redacted()
        result = diagnose(snapshot, KnowledgeStore(a.db))
        if a.output:
            a.output.parent.mkdir(parents=True, exist_ok=True)
            a.output.write_text(result.model_dump_json(indent=2) + "\n")
        else:
            print(result.model_dump_json(indent=2))
    elif a.cmd == "evaluate":
        print(json.dumps(evaluate_fixtures(a.fixtures), indent=2))
    else:
        fixture = Path(__file__).parent.parent / "fixtures" / "p0301.json"
        print(diagnose(SimulatedReader(fixture).read_snapshot()).model_dump_json(indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
