#!/usr/bin/env python3
"""Receipt engine: deterministic parts only. No model calls.

  python3 engine/review.py finalize RECEIPT.json [--repo sample] [--out FILE]
      Re-resolve every citation against git, recompute claim statuses and routing,
      then run the schema and invariant checks.
  python3 engine/review.py triage [--repo sample]
      Cheap pre-AI routing for the four sample branches, from requirement quality
      and diff shape alone.

Rules are plain code, tunable constants below. There is no numeric trust score:
every tier comes with the rules that fired and what was observed.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "schema"))

TIERS = ["light", "standard", "full_read"]
LARGE_SOURCE_LINES = 400  # changed lines in non-test, non-doc, non-generated files
EXECUTED = ("passed", "failed")


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


# ---------- citations ----------

def citation_resolves(repo, c):
    """True if the file exists at that SHA and the line range lies inside it."""
    try:
        n = len(git(repo, "show", f"{c['sha']}:{c['file']}").splitlines())
    except RuntimeError:
        return False
    return 1 <= c["startLine"] <= c["endLine"] <= n


# ---------- claim status ----------

def claim_status(claim, checks):
    """A behaviour claim is verified only through a named test that a cited check actually ran.

    Citing a check with no named test is not enough: a whole-suite pass does not show that
    this claim is exercised, so the claim waits for a human to confirm the link.
    """
    if not claim["citation"]["resolves"]:
        return "unsupported", "The citation does not resolve at the pinned revision."
    if claim["kind"] == "code_fact":
        return "source_only", "The citation resolves. The claim describes code; no executed check is needed or implied."
    cited = [checks[k] for k in claim["checkRefs"] if k in checks and checks[k]["status"] in EXECUTED]
    if not cited:
        return "unsupported", "A behaviour claim with no executed check behind it."
    refs = claim.get("testRefs", [])
    if not refs:
        return "needs_link_review", ("Cites " + ", ".join(c["id"] for c in cited)
                                     + " but names no test. That the check exercises this claim is not shown; a human must confirm the link.")
    found, missing = [], []
    for name in refs:
        hit = [(c, t) for c in cited for t in c.get("tests", []) if t["name"] == name and t["outcome"] in EXECUTED]
        (found if hit else missing).append((name, hit))
    if missing:
        return "unsupported", "Names a test that no cited check ran: " + ", ".join(n for n, _ in missing) + "."
    wrong = [f"{t['name']} in {c['id']} ({t['outcome']}, expected {c.get('expected', 'passed')})"
             for _, hit in found for c, t in hit if t["outcome"] != c.get("expected", "passed")]
    if wrong:
        return "contradicted", "A named test had the opposite outcome from what the claim needs: " + "; ".join(wrong) + "."
    return "verified", "Every named test ran with the outcome the claim needs: " + ", ".join(n for n, _ in found) + "."


# ---------- routing ----------

def bump(tier, new):
    return max(tier, new, key=TIERS.index)


def route(receipt):
    tier, reasons, focus = "light", [], []
    claims, checks = receipt["claims"], receipt["checks"]
    quality = receipt["requirement"]["quality"]

    if quality == "open_decision":
        tier = bump(tier, "full_read")
        reasons.append({"rule": "Requirement is an open product decision", "observed": "Whether the change is wanted is the maintainer's call, not the AI's."})
    elif quality == "contested":
        tier = bump(tier, "standard")
        reasons.append({"rule": "Requirement is contested", "observed": "The design direction is disputed in the issue."})
    elif quality == "weak":
        tier = bump(tier, "standard")
        reasons.append({"rule": "Requirement is weak", "observed": "The issue states little expected behaviour, so claims cannot be traced to it."})

    bad = [c for c in claims if c["status"] == "contradicted"]
    if bad:
        tier = bump(tier, "standard")
        reasons.append({"rule": "A claim is contradicted by an executed check", "observed": ", ".join(c["id"] for c in bad)})
    unlinked = [c for c in claims if c["status"] == "needs_link_review"]
    if unlinked:
        tier = bump(tier, "standard")
        reasons.append({"rule": "A claim cites a check but no named test: the link needs a human", "observed": ", ".join(c["id"] for c in unlinked)})
    weak = [c for c in claims if c["status"] == "unsupported"]
    if weak:
        tier = bump(tier, "standard")
        reasons.append({"rule": "A claim has no supporting evidence", "observed": ", ".join(c["id"] for c in weak)})
    for c in bad + weak + unlinked:
        ci = c["citation"]
        focus.append({"file": ci["file"], "lines": f"{ci['startLine']}-{ci['endLine']}", "why": f"{c['id']} is {c['status']}: {c['statusReason']}"})

    if receipt["outOfRequirement"]:
        tier = bump(tier, "standard")
        reasons.append({"rule": "The change goes beyond the requirement", "observed": ", ".join(o["id"] for o in receipt["outOfRequirement"])})
    if receipt["refusals"]:
        tier = bump(tier, "standard")
        reasons.append({"rule": "The AI refused to decide something the human must", "observed": ", ".join(r["id"] for r in receipt["refusals"])})
    failed = [c["id"] for c in checks if c["status"] == "failed" and c.get("expected", "passed") == "passed" and c.get("role", "gate") == "gate"]
    if failed:
        tier = bump(tier, "full_read")
        reasons.append({"rule": "A gate check that should pass failed", "observed": ", ".join(failed)})
    skipped = [c["id"] for c in checks if c["status"] in ("not_run", "unavailable", "skipped")]
    if skipped:
        reasons.append({"rule": "Some checks did not run (visible, not hidden)", "observed": ", ".join(skipped)})

    if not reasons:
        reasons.append({"rule": "Requirement clear, every claim verified or code-only, no scope change", "observed": "No rule asked for more human attention."})
    return {"tier": tier, "reasons": reasons, "humanFocus": focus}


# ---------- finalize ----------

def finalize(receipt, repo):
    for c in receipt["claims"]:
        c["citation"]["resolves"] = citation_resolves(repo, c["citation"])
    checks = {c["id"]: c for c in receipt["checks"]}
    for c in receipt["claims"]:
        c["status"], c["statusReason"] = claim_status(c, checks)
    old = receipt.get("routing", {}).get("humanFocus", [])
    receipt["routing"] = route(receipt)
    # Keep hand-added focus entries (for example about out-of-requirement files).
    seen = {(f["file"], f.get("lines")) for f in receipt["routing"]["humanFocus"]}
    receipt["routing"]["humanFocus"] += [f for f in old if (f["file"], f.get("lines")) not in seen]
    return receipt


# ---------- triage ----------

def classify(path):
    if ".g.cs" in path or "/Resources/" in path:
        return "generated"
    if path.startswith("tests/") or "/tests/" in path:
        return "tests"
    if path.endswith(".md") or path.startswith("doc/"):
        return "docs"
    return "source"


def triage(repo):
    reqs = json.loads((HERE / "requirements.json").read_text())
    rows = []
    for rid, r in reqs.items():
        head = git(repo, "rev-parse", f"origin/{r['branch']}").strip()
        base = git(repo, "rev-parse", f"{head}^").strip()
        lines = {"source": 0, "tests": 0, "docs": 0, "generated": 0}
        files = {"source": 0, "tests": 0, "docs": 0, "generated": 0}
        for row in git(repo, "diff", "--numstat", base, head).splitlines():
            add, dele, path = row.split("\t", 2)
            k = classify(path)
            files[k] += 1
            lines[k] += (int(add) if add != "-" else 0) + (int(dele) if dele != "-" else 0)
        reasons, tier = [], "light"
        q = r["quality"]
        if q == "open_decision":
            tier = bump(tier, "full_read"); reasons.append("open product decision: a human decides whether it is wanted")
        if q == "contested":
            tier = bump(tier, "standard"); reasons.append("contested requirement")
        if q == "weak":
            tier = bump(tier, "standard"); reasons.append("weak requirement")
        if lines["source"] > LARGE_SOURCE_LINES:
            tier = bump(tier, "full_read"); reasons.append(f"{lines['source']} changed source lines (limit {LARGE_SOURCE_LINES})")
        if not reasons:
            reasons.append("strong requirement and a small source change")
        rows.append((rid, head[:8], q, tier, files, lines, reasons))
    return rows


def print_triage(rows):
    for rid, head, q, tier, files, lines, reasons in rows:
        print(f"{rid:6} {head}  requirement={q:13} -> {tier.upper()}")
        print(f"       files: " + ", ".join(f"{k} {v}" for k, v in files.items()) + "   lines: " + ", ".join(f"{k} {v}" for k, v in lines.items()))
        print(f"       why:   " + "; ".join(reasons))
        if files["generated"]:
            print(f"       note:  {files['generated']} generated files can be machine-checked instead of read")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("finalize"); f.add_argument("receipt"); f.add_argument("--repo", default=str(ROOT / "sample")); f.add_argument("--out")
    t = sub.add_parser("triage"); t.add_argument("--repo", default=str(ROOT / "sample"))
    a = p.parse_args()

    if a.cmd == "triage":
        print_triage(triage(a.repo))
        return 0

    from validate import invariant_errors  # noqa: E402
    from jsonschema import Draft202012Validator
    receipt = finalize(json.loads(Path(a.receipt).read_text()), a.repo)
    out = Path(a.out or a.receipt)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    schema = json.loads((ROOT / "schema" / "receipt.schema.json").read_text())
    errs = [f"schema: {'/'.join(map(str, e.absolute_path))}: {e.message}" for e in Draft202012Validator(schema).iter_errors(receipt)]
    errs = errs or invariant_errors(receipt)
    for c in receipt["claims"]:
        print(f"{c['id']}  {c['status']:12} {c['text'][:70]}")
    print(f"routing: {receipt['routing']['tier'].upper()}")
    for r in receipt["routing"]["reasons"]:
        print(f"  - {r['rule']}: {r['observed']}")
    for e in errs:
        print("FAIL", e)
    print("OK" if not errs else f"{len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
