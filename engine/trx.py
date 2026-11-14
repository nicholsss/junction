#!/usr/bin/env python3
"""Read per-test results from a .trx file (dotnet test --logger trx).

  python3 engine/trx.py attach RECEIPT.json CHK1=evidence/trx/CHK1.trx ...

Sets `tests` on each named check from the raw file, replacing anything typed by hand,
and refuses if the counts disagree with what the check already records.
"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"t": "http://microsoft.com/schemas/VisualStudio/TeamTest/2010"}
OUTCOME = {"Passed": "passed", "Failed": "failed", "NotExecuted": "skipped"}


def short(name):
    """Namespace.Class.Method -> Class.Method, the form dotnet prints for failures."""
    head, paren, tail = name.partition("(")
    return ".".join(head.split(".")[-2:]) + paren + tail


def read_trx(path):
    root = ET.parse(path).getroot()
    out = []
    for r in root.iterfind(".//t:UnitTestResult", NS):
        out.append({"name": short(r.get("testName")), "outcome": OUTCOME.get(r.get("outcome"), "skipped")})
    return sorted(out, key=lambda t: t["name"])


def attach(receipt, mapping):
    by_id = {c["id"]: c for c in receipt["checks"]}
    for cid, path in mapping.items():
        tests = read_trx(path)
        c = by_id[cid]
        n = {k: sum(1 for t in tests if t["outcome"] == k) for k in ("passed", "failed")}
        rec = c.get("counts", {})
        if rec and (rec.get("passed"), rec.get("failed"), rec.get("total")) != (n["passed"], n["failed"], len(tests)):
            raise SystemExit(f"{cid}: trx has {n['passed']} passed, {n['failed']} failed, {len(tests)} total; "
                             f"receipt records {rec}. Not attaching.")
        c["tests"] = tests
    return receipt


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] != "attach":
        raise SystemExit(__doc__)
    path = Path(sys.argv[2])
    receipt = attach(json.loads(path.read_text()), dict(a.split("=", 1) for a in sys.argv[3:]))
    path.write_text(json.dumps(receipt, indent=2) + "\n")
    for c in receipt["checks"]:
        if "tests" in c:
            print(c["id"], len(c["tests"]), "tests")
