#!/usr/bin/env python3
"""Ask a model to propose claims, refusals and out-of-requirement items for one change.

  python3 engine/propose.py BASE_RECEIPT.json [--out FILE] [--inject-bad] [--dry-run]

BASE_RECEIPT supplies the requirement, subject and executed checks (the harness's
evidence). The model sees those plus the annotated diff, and returns JSON. It never
sets a status: every claim is passed through engine/review.py finalize, which
re-resolves citations and computes statuses from the executed checks.

--inject-bad appends claims that are wrong on purpose, to show the engine catching them.
Standard library only. Reads VERDA_API_KEY (and optional VERDA_BASE_URL, VERDA_MODEL) from .env.
"""
import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import review  # noqa: E402

DEFAULT_URL = "https://inference.verda.com/v1"
DEFAULT_MODEL = "deepseek-4-1-flash-1017"


def load_env():
    env = {}
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def annotated_diff(repo, base, head):
    """Unified diff where every added or context line carries its line number in the head file."""
    out = []
    raw = review.git(repo, "diff", "-U3", base, head)
    new_no = 0
    for line in raw.splitlines():
        if line.startswith("diff --git"):
            out.append(f"\n=== {line.split(' b/')[-1]}")
        elif line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            new_no = int(m.group(1))
            out.append(line)
        elif line.startswith(("---", "+++", "index ", "new file", "deleted file")):
            continue
        elif line.startswith("-"):
            out.append(f"      {line}")
        else:
            out.append(f"{new_no:5} {line}")
            new_no += 1
    return "\n".join(out)


SYSTEM = """You are a code reviewer producing evidence for a human who must decide whether to accept an AI-written change without reading all of it.
Rules:
- Cite only lines shown in the diff, using the head-file line numbers printed at the left. Use a file path exactly as shown after '==='.
- Each claim is either kind "code_fact" (describes what the cited code says) or "behaviour" (asserts what happens at run time).
- For a behaviour claim, list in checkRefs the ids of executed checks that would support it, and in testRefs the exact names of the specific tests (from the test list) that exercise the claim. A check passing as a whole is not evidence for a specific claim; name the test that is. If no listed test exercises the claim, use empty lists; do not invent evidence or test names.
- Cover every acceptance criterion: where a listed test exercises it, write a behaviour claim that names that test and the checks it ran in, including a claim about whether a new test fails on the base source and passes on the head. Do not describe tests only as code.
- Never state that something is verified or passes. You do not set statuses.
- Put in outOfRequirement anything the change does that the requirement does not ask for.
- Put in refusals the questions a human owner must decide, which you will not decide, with the reason.
- Put in unknowns what was not checked.
Return one JSON object only, with keys: claims, refusals, outOfRequirement, unknowns.
claims: [{"text","kind","file","startLine","endLine","requirementRefs":["AC1"],"checkRefs":["CHK2"],"testRefs":["Class.Method"],"note"}]
refusals: [{"question","whyAiRefused"}]
outOfRequirement: [{"description"}]
unknowns: [{"text"}]
Give 4 to 8 claims."""


def build_prompt(receipt, diff):
    req = receipt["requirement"]
    ac = "\n".join(f"{a['id']} ({a['origin']}): {a['text']}" for a in req["acceptanceCriteria"])
    checks = "\n".join(
        f"{c['id']} [{c['status']}, supports a claim when it {c.get('expected', 'passed')}] {c['description']} (scope: {c['scope']})"
        for c in receipt["checks"]
    )
    names = sorted({t["name"] for c in receipt["checks"] for t in c.get("tests", [])})
    per_check = []
    for c in receipt["checks"]:
        if "tests" in c:
            ran = {t["name"]: t["outcome"] for t in c["tests"]}
            per_check.append(f"{c['id']}: {len(ran)} tests ran. Failed: {sorted(n for n, o in ran.items() if o == 'failed') or 'none'}. "
                             f"Not run in this check: {[n for n in names if n not in ran] or 'none'}.")
    tests = ("Test names (each check below says which failed or did not run; every other listed test passed in that check):\n"
             + "\n".join(names) + "\n" + "\n".join(per_check) + "\n\n") if names else ""
    return (
        f"Requirement {req['id']}: {req.get('title', '')}\nAcceptance criteria:\n{ac}\n\n"
        f"Executed checks (harness results, not yours to change):\n{checks}\n\n{tests}"
        f"Diff, head-file line numbers on the left:\n{diff}"
    )


def call_model(env, system, user):
    url = env.get("VERDA_BASE_URL", DEFAULT_URL).rstrip("/") + "/chat/completions"
    body = {
        "model": env.get("VERDA_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "max_tokens": 6000,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + env["VERDA_API_KEY"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"model call failed: HTTP {e.code} {e.read()[:300].decode(errors='replace')}")
    return body["model"], data["choices"][0]["message"]["content"], data.get("usage")


def assemble(base, proposal, model):
    """Turn model output into receipt sections. Structure is enforced; truth is not decided here."""
    checks = {c["id"]: c for c in base["checks"]}
    acs = {a["id"] for a in base["requirement"]["acceptanceCriteria"]}
    head = base["subject"]["headSha"]
    claims, notes = [], []
    for i, c in enumerate(proposal.get("claims", []), 1):
        try:
            kind = c["kind"] if c["kind"] in ("code_fact", "behaviour") else "behaviour"
            start, end = int(c["startLine"]), int(c["endLine"])
            file = str(c["file"])
            text = str(c["text"])
        except (KeyError, TypeError, ValueError):
            notes.append(f"claim {i} dropped: malformed")
            continue
        refs, stripped = [], []
        for k in c.get("checkRefs", []):
            ok = k in checks and checks[k]["status"] in review.EXECUTED
            if ok and kind == "behaviour":
                refs.append(k)
            else:
                stripped.append(k)
        note = str(c.get("note", ""))
        if stripped:
            note += f" [engine removed check refs {stripped}: unknown, not run, or attached to a code_fact]"
        claims.append({
            "id": f"CLM{len(claims) + 1}", "kind": kind, "text": text, "modelNote": note.strip(),
            "citation": {"file": file, "sha": head, "startLine": max(start, 1), "endLine": max(end, 1), "resolves": False},
            "requirementRefs": [a for a in c.get("requirementRefs", []) if a in acs],
            "checkRefs": refs,
            "testRefs": [str(t) for t in c.get("testRefs", [])] if kind == "behaviour" else [], "status": "unsupported", "statusReason": "pending",
        })
    return {
        "claims": claims,
        "refusals": [{"id": f"REF{i}", "question": str(x["question"]), "whyAiRefused": str(x["whyAiRefused"])}
                     for i, x in enumerate(proposal.get("refusals", []), 1) if "question" in x and "whyAiRefused" in x],
        "outOfRequirement": [{"id": f"OOR{i}", "description": str(x["description"]), "evidenceRefs": []}
                             for i, x in enumerate(proposal.get("outOfRequirement", []), 1) if "description" in x],
        "unknowns": [{"id": f"UNK{i}", "text": str(x["text"])}
                     for i, x in enumerate(proposal.get("unknowns", []), 1) if "text" in x],
    }, notes


def bad_claims(base, first_file):
    head = base["subject"]["headSha"]
    def mk(text, kind, start, end, refs, why, tests=()):
        return {"kind": kind, "text": text, "modelNote": "INJECTED TEST CLAIM: " + why,
                "citation": {"file": first_file, "sha": head, "startLine": start, "endLine": end, "resolves": False},
                "requirementRefs": [], "checkRefs": refs, "testRefs": list(tests), "status": "unsupported", "statusReason": "pending"}
    return [
        mk("The patch handles every closed generic shape without regression.", "behaviour", 99999, 99999, ["CHK2"],
           "cites a line that does not exist, with a passing check attached"),
        mk("The change is safe for all consumers of the generator.", "behaviour", 239, 239, [],
           "a behaviour claim with no check at all"),
        mk("Referenced-assembly diagnostics are unchanged for every analyzer.", "behaviour", 239, 239, ["CHK4"],
           "names a test that failed in CHK4, the opposite of what a claim of no regression needs",
           ["GenericsFormatterTests.ClosedGenericStruct_FromMetadataReference_UnkeyedMember"]),
        mk("The generator never crashes on referenced generic types.", "behaviour", 239, 239, ["CHK2"],
           "names a test that does not exist", ["GenericsFormatterTests.EverythingWorks"]),
        mk("Closed generic structs from a referenced assembly build and get a resolver.", "behaviour", 239, 239, ["CHK2"],
           "cites the whole suite and names no test, though the claim is true: the engine must hold it for review"),
    ]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("base_receipt")
    p.add_argument("--repo", default=str(ROOT / "sample"))
    p.add_argument("--out")
    p.add_argument("--raw-out", help="Optional raw model response path, to keep live and measurement runs separate")
    p.add_argument("--inject-bad", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="print the prompt size and stop; no model call")
    a = p.parse_args()

    base = json.loads(Path(a.base_receipt).read_text())
    s = base["subject"]
    prompt = build_prompt(base, annotated_diff(a.repo, s["baseSha"], s["headSha"]))
    if a.dry_run:
        print(f"prompt: {len(prompt)} characters")
        return 0
    env = load_env()
    if not env.get("VERDA_API_KEY"):
        raise SystemExit("VERDA_API_KEY is empty. Put it in .env (see .env.example).")

    model, raw, usage = call_model(env, SYSTEM, prompt)
    rid = base["requirement"]["id"].lstrip("#")
    raw_path = Path(a.raw_out) if a.raw_out else ROOT / "evidence" / f"propose-{rid}.raw.json"
    raw_path.write_text(json.dumps({"model": model, "usage": usage, "content": raw}, indent=2) + "\n")
    try:
        proposal = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit(f"model did not return JSON; raw saved to {raw_path}")

    parts, notes = assemble(base, proposal, model)
    if a.inject_bad:
        first = next((c["citation"]["file"] for c in parts["claims"]), s.get("filesChanged", [""])[0])
        for c in bad_claims(base, first):
            c["id"] = f"CLM{len(parts['claims']) + 1}"
            parts["claims"].append(c)
    receipt = {
        "schemaVersion": "0.1",
        "receiptId": base["receiptId"].replace("example", "model") if "example" in base["receiptId"] else base["receiptId"] + "-model",
        "provenance": {"claimsSource": "model", "model": model,
                       "notes": "Claims, refusals, out-of-requirement items and unknowns proposed by the model; statuses computed by the engine."
                                + (" Includes deliberately wrong injected claims." if a.inject_bad else "")},
        "requirement": base["requirement"], "subject": s, "checks": base["checks"],
        **parts,
        "routing": {"tier": "light", "reasons": [{"rule": "pending", "observed": "pending"}], "humanFocus": []},
        "decision": {"status": "pending"},
    }
    out = Path(a.out or ROOT / "examples" / f"receipt-{rid}.model.json")
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"model {model}, usage {usage}")
    for n in notes:
        print("note:", n)
    print(f"wrote {out}; raw response in {raw_path}")
    print(f"next: python3 engine/review.py finalize {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
