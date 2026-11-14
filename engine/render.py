#!/usr/bin/env python3
"""Render the walkthrough page from receipts.

  python3 engine/render.py                 # writes walkthrough/index.html
  python3 engine/render.py --out FILE

Inputs (all JSON, nothing is recomputed here):
  examples/receipt-2283.live.json      the receipt shown in full
  examples/receipt-2283.model.json     the model-generated run, shown in Measurement
  examples/triage.json                 snapshot of `review.py triage` on the four samples

The page is one static file: HTML rendered here, CSS and a little JS inline. Reading
needs no JS. JS switches views and drafts a GitHub decision comment; it never signs.
Only engine/pr.py can apply a human comment to the receipt. Statuses and routing are copied from the receipt.
"""
import argparse
import html
import json
from pygments import highlight
from pygments.lexers import CSharpLexer, TextLexer, MarkdownLexer
from pygments.formatters import HtmlFormatter
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import decision  # noqa: E402

ROOT = HERE.parent
RECEIPT = ROOT / "examples" / "receipt-2283.live.json"
PR_FILE = ROOT / "docs" / "pull-requests.json"
DECISION_JS = (HERE / "decision.js").read_text()

def pr_rows():
    return json.loads(PR_FILE.read_text()) if PR_FILE.exists() else []

def receipt_pr(r):
    return next((x for x in pr_rows() if x["requirement"] == r["requirement"]["id"]), {})

def decision_label(r):
    d = r["decision"]
    if d["status"] == "pending":
        return "Decision: pending, no one has signed"
    if d["status"] == "escalated":
        return "Decision: escalated, pending owner judgement"
    if receipt_pr(r).get("status") == "pending":
        return "Decision: awaiting revalidation"
    return "Decision: " + d["status"].replace("_", " ") + " by " + d["owner"]


def status_label(r):
    """Human-facing status. Escalation stays pending, but is not an unread decision."""
    if r["decision"]["status"] == "escalated":
        return "pending owner judgement"
    return receipt_pr(r).get("status", "pending")


MODEL_RUN = ROOT / "examples" / "receipt-2283.model.json"
TRIAGE = ROOT / "examples" / "triage.json"
OUT = ROOT / "walkthrough" / "index.html"

e = html.escape
REQUIREMENTS_URL = "https://github.com/nicholsss/junction/blob/main/docs/DEMO_REQUIREMENTS.md"


def local_requirement_id(value):
    """Display historical sample IDs as local demo requirements, never GitHub issue tags."""
    return "R" + value.lstrip("#") if value.startswith("#") else value


# ---------------------------------------------------------------- vocabulary

STATUS = {
    "verified": ("Test-backed", "check"),
    "contradicted": ("Contradicted", "xcircle"),
    "unsupported": ("Unsupported", "alert"),
    "needs_link_review": ("Link needs review", "link"),
    "source_only": ("Source only", "file"),
}
STATUS_ORDER = ["verified", "contradicted", "unsupported", "needs_link_review", "source_only"]
CHECK_STATUS = {"passed": ("Passed", "check", "verified"), "failed": ("Failed", "xcircle", "contradicted"),
                "not_run": ("Not run", "dashed", "notrun"),
                "skipped": ("Skipped", "dashed", "notrun"),
                "unavailable": ("Unavailable", "alert", "unsupported")}
TIER = {"light": "Light", "standard": "Standard", "full_read": "Full read"}
TIER_TEXT = {
    "light": "A short look is enough, but a named human still decides.",
    "standard": "Work through the decision brief, the risks and the unknowns, then decide. Source is optional.",
    "full_read": "A human reads the whole change. The no-code brief is a starting point, not a substitute.",
}
ICON = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "xcircle": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "dashed": '<circle cx="12" cy="12" r="10" stroke-dasharray="3 3"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "arrow": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
}


def icon(name, cls="ic"):
    return f'<svg class="{cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICON[name]}</svg>'


def chip(status):
    label, ic = STATUS[status]
    return f'<span class="chip s-{status}">{icon(ic)}{e(label)}</span>'


def check_chip(status):
    label, ic, cls = CHECK_STATUS[status]
    return f'<span class="chip s-{cls}">{icon(ic)}{e(label)}</span>'


def tier_badge(tier, big=False):
    return f'<span class="tier t-{tier}{" big" if big else ""}">{e(TIER[tier])}</span>'


def short(sha):
    return sha[:8]


def mono(text):
    return f"<code>{e(text)}</code>"


def stacked(parts, label):
    """parts: [(css-class, text, count)]. One horizontal bar, counts inside, legend below."""
    total = sum(c for _, _, c in parts) or 1
    segs = "".join(
        f'<span class="seg {cls}" style="flex:{c} 1 0" title="{e(text)}: {c}">{c}</span>' for cls, text, c in parts if c)
    legend = "".join(f'<span class="lg"><i class="sw {cls}"></i>{e(text)} {c}</span>' for cls, text, c in parts if c)
    desc = ", ".join(f"{text} {c}" for _, text, c in parts if c)
    return (f'<div class="bar" role="img" aria-label="{e(label)}: {e(desc)}">{segs}</div>'
            f'<div class="legend">{legend}</div>')


# ---------------------------------------------------------------- data helpers

def test_outcome(check, name):
    for t in check.get("tests", []):
        if t["name"] == name:
            return t["outcome"]
    return None


def find_checks(r):
    cs = r["checks"]
    head = next((c for c in cs if c.get("revision") == "head" and c.get("tests")), None)
    fail = next((c for c in cs if c.get("expected") == "failed" and c.get("role") != "probe"), None)
    probe = next((c for c in cs if c.get("role") == "probe"), None)
    return head, fail, probe


# ---------------------------------------------------------------- sections

def automation_notice(r):
    path = ROOT / 'examples/automation-state.json'
    if not path.exists():
        return '<p class="snapshot-note">Snapshot · automation setup pending. Post decisions on GitHub.</p>'
    state = json.loads(path.read_text())
    if state.get('receiptHead') != r['subject']['headSha']:
        return '<p class="snapshot-note" data-stale="true">Publication state does not match this receipt. Verify the current PR before deciding.</p>'
    stale = state.get('stale', False)
    return ('<div class="snapshot-note" role="status" data-stale="' + str(stale).lower() + '"><b>'
            + ('Evidence outdated — fresh review required.' if stale else 'Published review snapshot')
            + '</b> · ' + e(state['updatedAt']) + '<br>' + e(state['message'])
            + (f' <a href="{e(state["runUrl"])}">Processing run</a>' if state.get('runUrl') else '') + '</div>')


def render_header(r):
    s, q = r["subject"], r["requirement"]
    return f"""
<header class="rhead">
  <div class="overline">HackJunction 2026 · {e(local_requirement_id(q['id']))}</div>
  <h1>Fix a crash when generating serializers</h1>
  <p class="muted">Check the evidence and judge the remaining risks. Source is optional.</p>
  <div class="meta">
    <span><a href="{e(receipt_pr(r).get('url', '#'))}">PR #{receipt_pr(r).get('number', '—')}</a></span><span class="technical-meta">Base {mono(short(s['baseSha']))}</span>
    <span>Head {mono(short(s['headSha']))}</span>
    <span><a href="{REQUIREMENTS_URL}#{local_requirement_id(q['id']).lower()}">Demo requirement</a></span>
  </div>
  <div class="prov">
    <span class="tag" id="decision-tag" data-state="pending">{icon('user')}<span>{e(decision_label(r))}</span></span>
  </div>
  {automation_notice(r)}
  <div id="decision-banner" class="banner" hidden></div>
</header>"""


def render_rail(r):
    rt = r["routing"]
    reasons = "".join(
        f'<li><span class="rule">{e(x["rule"])}</span><span class="obs">{e(x["observed"])}</span></li>' for x in rt["reasons"])
    unk = "".join(f"<li>{e(u['text'])}</li>" for u in r.get("unknowns", []))
    return f"""
<aside class="rail" aria-label="Routing and limits">
  <section class="card">
    <div class="overline">Review depth</div>
    {tier_badge(rt['tier'], True)}
    <p class="muted">{e(TIER_TEXT[rt['tier']])} A rule set this, not a score.</p>
    <div class="overline">Rules that fired</div>
    <ul class="rules">{reasons}</ul>
  </section>
  <section class="card limits">
    <div class="overline">What this does not cover</div>
    <ul>{unk or '<li>No residual unknowns were recorded.</li>'}</ul>
    <p class="muted small">Nothing here establishes long-term reliability, and a clean classification is not a clean bill of health.</p>
  </section>
</aside>"""


def render_focus(r):
    items = []
    for f in r["routing"]["humanFocus"]:
        ln = f.get("lines", "")
        a, _, b = ln.partition("-")
        if a and a == b:
            ln = a
        base = f["file"].rsplit("/", 1)[-1]
        folder = f["file"][: -len(base)]
        items.append(f'<li><div><code class="where">{e(base + (":" + ln if ln else ""))}</code>'
                     f'<div class="muted small path">{e(folder)}</div></div><span>{e(f["why"])}</span></li>')
    return f"""
<section class="sec" id="read-first">
  <h2>Optional source focus</h2>
  <p class="lede">Corroboration only, not a required reading list. Every decision-critical point appears above in normal text.</p>
  <ul class="focus">{''.join(items)}</ul>
  <div class="note">{icon('info')}<span><b>Source is optional.</b> Opening these files may help check the AI's interpretation, but the decision brief, recorded checks, classification reasons and unknowns are the no-code path. A citation that resolves does not show that the cited lines support the claim.</span></div>
</section>"""


def render_coverage(r):
    claims = r["claims"]
    rows = []
    for ac in r["requirement"]["acceptanceCriteria"]:
        mine = [c for c in claims if ac["id"] in c.get("requirementRefs", [])]
        chips = "".join(
            f'<a class="cl" href="#claim-{e(c["id"])}" data-open="claim-{e(c["id"])}">{mono(c["id"])}{chip(c["status"])}</a>' for c in mine
        ) or '<span class="chip s-notrun">' + icon("dashed") + "No claim covers this</span>"
        rows.append(f'<tr><td><code>{e(ac["id"])}</code></td><td>{e(ac["text"])}<span class="origin o-{e(ac["origin"])}">{e(ac["origin"])}</span></td><td class="chips">{chips}</td></tr>')
    return f"""
<section class="sec" id="coverage">
  <h2>Requirement to evidence</h2>
  <p class="lede">Each acceptance criterion, and the claims that touch it. <b>Stated</b> criteria come from the issue; <b>derived</b> ones are ours and labelled as such.</p>
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>ID</th><th>Criterion</th><th>Claims</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
</section>"""


def render_claims(r):
    claims = r["claims"]
    checks = {c["id"]: c for c in r["checks"]}
    counts = {s: sum(1 for c in claims if c["status"] == s) for s in STATUS_ORDER}
    bar = stacked([(f"s-{s}", STATUS[s][0], counts[s]) for s in STATUS_ORDER], "Claims by status")
    ac_text = {a["id"]: a["text"] for a in r["requirement"]["acceptanceCriteria"]}
    out = []
    for c in claims:
        cit = c["citation"]
        lines = f"{cit['startLine']}" if cit["startLine"] == cit["endLine"] else f"{cit['startLine']}-{cit['endLine']}"
        where = f"{cit['file']}:{lines}"
        req = "".join(f'<li><code>{e(a)}</code> {e(ac_text.get(a, ""))}</li>' for a in c.get("requirementRefs", [])) or '<li class="muted">No criterion cited. This claim goes beyond the requirement.</li>'
        if c.get("testRefs"):
            trows = []
            for t in c["testRefs"]:
                cells = []
                for cid in c["checkRefs"]:
                    ck = checks.get(cid)
                    o = test_outcome(ck, t) if ck else None
                    cls = {"passed": "verified", "failed": "contradicted"}.get(o, "notrun")
                    cells.append(f'<span class="mini s-{cls}">{e(cid)}: {e(o or "not in this check")}</span>')
                trows.append(f'<li><code>{e(t)}</code><div class="minis">{"".join(cells)}</div></li>')
            tests = f'<ul class="tests">{"".join(trows)}</ul>'
        elif c["checkRefs"]:
            tests = '<p class="muted">Cites a check but names no test. A human must judge the link.</p>'
        else:
            tests = '<p class="muted">No executed check.</p>'
        result = f'{chip(c["status"])}'
        note = f'<div class="why"><div class="overline">Author’s note</div><p>{e(c["modelNote"])}</p></div>' if c.get("modelNote") else ""
        out.append(f"""
<details class="claim" id="claim-{e(c['id'])}"{' open' if c['status'] == 'contradicted' else ''}>
  <summary>
    {chip(c['status'])}
    <code class="cid">{e(c['id'])}</code>
    <span class="ctext">{e(c['text'])}</span>
    <span class="kind">{e(c['kind'].replace('_', ' '))}</span>
  </summary>
  <div class="claimbody">
    <ol class="chain">
      <li><div class="overline">Requirement</div><ul class="plain">{req}</ul></li>
      <li><div class="overline">Claim</div><p>{e(c['text'])}</p></li>
      <li><div class="overline">Cited lines</div><code class="where">{e(where)}</code><div class="muted small">at {e(short(cit['sha']))}, {'resolves' if cit['resolves'] else 'does not resolve'}</div></li>
      <li><div class="overline">Named tests</div>{tests}</li>
      <li><div class="overline">Result</div>{result}</li>
    </ol>
    <div class="why"><div class="overline">Why the engine gave this status</div><p>{e(c['statusReason'])}</p></div>
    {note}
  </div>
</details>""")
    return f"""
<section class="sec" id="claims">
  <h2>Claims</h2>
  <p class="lede">What the change says it does. A status is computed by the engine from executed checks; the author never sets it. <b>Test-backed</b> means a named test ran with the expected outcome; relevance to the whole claim remains unproven. Archived JSON calls this status verified.</p>
  {bar}
  <div class="claims">{''.join(out)}</div>
</section>"""


def render_fail_then_pass(r):
    head, fail, probe = find_checks(r)
    if not (head and fail):
        return ""
    names = [t["name"] for t in fail["tests"] if t["outcome"] == "failed"]
    if not names:
        return ""

    def cell(ck, name, good):
        o = test_outcome(ck, name) if ck else None
        if o is None:
            return '<td><span class="mini s-notrun">not run</span></td>'
        ok = (o == "passed") == good
        cls = "verified" if ok else "contradicted"
        return f'<td><span class="mini s-{cls}">{e(o)}</span></td>'

    rows = []
    for n in names:
        cls_, _, meth = n.partition(".")
        cells = cell(fail, n, False) + cell(head, n, True)
        if probe:
            cells += cell(probe, n, True)
        rows.append(f'<tr><td><code>{e(meth)}</code><div class="muted small">{e(cls_)}</div></td>{cells}</tr>')
    probe_head = (f'<th>Comparison fix<br><span class="muted small">{e(probe["id"])}: should pass</span></th>'
                  if probe else "")
    probe_note = ""
    if probe:
        changed = [n for n in names if test_outcome(probe, n) == "failed"]
        if changed:
            probe_note = (' The comparison column shows tests that behave differently in a crash-only fix; '
                          'that is comparison evidence, not a broken build.')
    return f"""
<section class="sec" id="fail-then-pass">
  <h2>Do the AI’s new tests detect the bug?</h2>
  <p class="lede">A test that only passes proves little. These ran against the base source and the AI patch{f', plus a comparison fix' if probe else ''}. Green is the outcome that supports the AI patch, red is the opposite{f'; a comparison probe is not a merge gate' if probe else ''}.</p>
  <div class="tablewrap"><table class="grid ftp">
    <thead><tr><th>New test</th><th>Base source<br><span class="muted small">{e(fail['id'])}: should fail</span></th><th>AI patch<br><span class="muted small">{e(head['id'])}: should pass</span></th>{probe_head}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
  <div class="note">{icon('info')}<span>The base failures and patch passes support the crash fix <i>in the tested scenarios</i>. They do not establish other trigger-matrix shapes, other diagnostic kinds, or the unrun two-project reproduction.{probe_note}</span></div>
</section>"""


def render_checks(r):
    cards = []
    for c in r["checks"]:
        cnt = c.get("counts")
        bar = ""
        if cnt:
            bar = stacked([("s-verified", "passed", cnt["passed"]), ("s-contradicted", "failed", cnt["failed"])], f"{c['id']} results")
        badges = ""
        if c.get("expected") == "failed":
            badges += '<span class="tag">Expected to fail</span>'
        if c.get("role") == "probe":
            badges += '<span class="tag">Probe, not a gate</span>'
        cmd = f'<div class="kv"><span>Command</span><code>{e(c["command"])}</code></div>' if c.get("command") else ""
        out = f'<div class="kv"><span>Output</span><code>{e(c["outputRef"])}</code></div>' if c.get("outputRef") else ""
        fails = ""
        if c.get("failures"):
            fails = '<div class="kv"><span>Failures</span><ul class="plain">' + "".join(f"<li><code>{e(f)}</code></li>" for f in c["failures"]) + "</ul></div>"
        cards.append(f"""
<article class="card check" id="check-{e(c['id'])}">
  <div class="chead"><code>{e(c['id'])}</code>{check_chip(c['status'])}{badges}</div>
  <h3>{e(c['description'])}</h3>
  {bar}
  <div class="kv"><span>Revision</span><span>{e(c['revision'])}</span></div>
  <div class="kv"><span>Scope</span><span>{e(c['scope'])}</span></div>
  <div class="kv"><span>Limits</span><span>{e(c['limitations'].replace('upstream PR #2305', 'the reference patch'))}</span></div>
  {cmd}{out}{fails}
</article>""")
    return f"""
<section class="sec" id="checks">
  <h2>Executed checks, and what they do not cover</h2>
  <p class="lede">Written only by the harness. Failed, skipped and not-run checks stay visible. Here, a failed check can be the useful result, and the card says when.</p>
  <div class="checks">{''.join(cards)}</div>
</section>"""


FINDING_LABELS = {
    "accept_scope": ("Accept scope", "The extra change is acceptable for this decision."),
    "change_required": ("Change required", "This change should not be accepted as it stands."),
    "needs_owner": ("Needs owner judgement", "A code or domain owner must judge this scope."),
}
# IDs come from the shared contract; labels are presentation only.
FINDING_POSITIONS = [(pid, *FINDING_LABELS[pid]) for pid in decision.FINDING_POSITIONS]


def evidence_refs(refs):
    """Link a decision-brief reference to its detail. IDs are receipt-defined, never user input."""
    labels = []
    for ref in refs:
        prefix = ref.rstrip("0123456789")
        target = {"AC": "coverage", "CHK": "check-" + ref, "CLM": "claim-" + ref,
                  "REF": "refusal-" + ref, "OOR": "finding-" + ref, "UNK": "unknown-" + ref}.get(prefix)
        labels.append(f'<a href="#{e(target)}" data-open="{e(target)}">{mono(ref)}</a>' if target else mono(ref))
    return " ".join(labels)


def render_brief(r):
    statements = r.get("decisionBrief", [])
    if not statements:
        return ""
    section_order = [("intent", "Requirement intent"), ("supported", "What the evidence supports"),
                     ("risk", "Material risks"), ("limit", "Limits"),
                     ("reliability", "How reliable are the AI's claims?")]
    provenance = {"harness": "Harness observation", "model": "AI interpretation",
                  "team": "Team explanation"}
    groups = []
    for key, title in section_order:
        mine = [x for x in statements if x["section"] == key]
        if not mine:
            continue
        items = "".join(
            f'<li class="brief-item"><span class="provtag p-{e(x["provenance"])}">{icon("check" if x["provenance"] == "harness" else "user" if x["provenance"] == "team" else "info")}{e(provenance.get(x["provenance"], x["provenance"]))}</span>'
            f'<span>{e(x["text"])}</span><span class="briefrefs">{evidence_refs(x["evidenceRefs"])}</span></li>'
            for x in mine)
        groups.append(f'<div class="briefgroup"><div class="overline">{e(title)}</div><ul class="brief">{items}</ul></div>')
    return f"""
<section class="sec" id="brief">
  <h2>Decision brief</h2>
  <p class="muted">Recorded explanations and their sources. These are not human decisions.</p>
  {render_at_a_glance(r)}
  {''.join(groups)}
  <div class="note">{icon('info')}<span><b>No trust or hallucination score.</b> Mechanical claim classifications are evidence links, not semantic verdicts. A real citation can still support a wrong interpretation, and a passing test can miss a defect.</span></div>
</section>"""


def render_at_a_glance(r):
    claims = r["claims"]
    counts = {s: sum(1 for c in claims if c["status"] == s) for s in STATUS_ORDER}
    head, fail, probe = find_checks(r)
    parts = [f'<b>{counts["verified"]} of {len(claims)}</b> AI claims are test-backed']
    others = [f'{counts[s]} {STATUS[s][0].lower()}' for s in ("contradicted", "unsupported", "needs_link_review", "source_only") if counts[s]]
    if others:
        parts.append("; " + ", ".join(others))
    if head and head.get("counts"):
        parts.append(f'. The patch suite recorded <b>{head["counts"]["passed"]} passed of {head["counts"]["total"]}</b> tests ({mono(head["id"])})')
    if fail and fail.get("counts"):
        parts.append(f'; on base source, <b>{fail["counts"]["failed"]} failed of {fail["counts"]["total"]}</b> ({mono(fail["id"])}, expected failure)')
    return f'<div class="glance">{"".join(parts)}.</div>'


def render_findings(r):
    items = []
    for o in r.get("outOfRequirement", []):
        refs = " ".join(mono(x) for x in o.get("evidenceRefs", []))
        choices = "".join(
            f'<label><input type="radio" name="find-{e(o["id"])}" value="{e(pid)}"> {e(label)}'
            f'<span class="muted small">{e(why)}</span></label>'
            for pid, label, why in FINDING_POSITIONS)
        items.append(f"""
<article class="card finding" id="finding-{e(o['id'])}" data-finding="{e(o['id'])}">
  <div class="chead"><code>{e(o['id'])}</code><span class="tag warn">Outside the requirement</span></div>
  <p>{e({'OOR1': 'The patch also adds README guidance.', 'OOR2': 'The patch also adds analyzer documentation.'}.get(o['id'], o['description']))}</p>
  <details class="risk-context"><summary>Scope details</summary><p>{e(o['description'])}</p><p>Evidence: {refs or 'none recorded'}</p></details>
  <fieldset class="seg3" aria-describedby="err-{e(o['id'])}"><legend>Your position, required only to accept</legend>{choices}</fieldset>
  <p class="field-error" id="err-{e(o['id'])}" hidden></p>
  <details class="risk-context"><summary>Add an optional note</summary><label class="ans">Note
    <input type="text" name="note-{e(o['id'])}" data-note-for="{e(o['id'])}" placeholder="Optional context; leave blank if none">
  </label></details>
</article>""")
    if not items:
        return ""
    return f"""
<section class="sec" id="found">
  <h3>Additional scope</h3>

  <div class="stack">{''.join(items)}</div>
</section>"""


def render_refusals(r):
    recorded = {p["refusalId"]: p for p in r["decision"].get("refusalPositions", [])}
    items = []
    for f in r.get("refusals", []):
        rel = " ".join(mono(x) for x in f.get("relatedClaims", []) + f.get("relatedChecks", []))
        options = "".join(
            f'<option value="{e(p["id"])}">{e(p["label"])} [{e(p["effect"].replace("_", " "))}]</option>'
            for p in f.get("positions", []))
        chosen = recorded.get(f["id"])
        answer = (f'<p><b>Recorded human position:</b> {mono(chosen["positionId"])}'
                  + (f' — {e(chosen["note"])}' if chosen.get("note") else "") + '</p>') if chosen else ""
        items.append(f"""
<article class="card refusal" id="refusal-{e(f['id'])}" data-refusal="{e(f['id'])}">
  <div class="chead"><code>{e(f['id'])}</code><span class="tag ask">The AI refused to decide</span></div>
  <h3>{e({'REF1': 'Allow diagnostics from referenced code to be hidden?', 'REF2': 'Accept the documentation assumption about other assemblies?'}.get(f['id'], f['question']))}</h3>
  <p>{e({'REF1': 'The patch drops diagnostics in referenced code; the crash-only comparison still reports MsgPack004.', 'REF2': 'The docs assume dependencies run the analyzer. That assumption was not checked.'}.get(f['id'], f['whyAiRefused']))}</p>
  <details class="risk-context"><summary>Context and original question</summary><p>{e(f['question'])}</p><p>{e(f['whyAiRefused'])}</p></details>
  {f'<p class="muted small">Related: {rel}</p>' if rel else ''}
  {answer}
  <label class="ans">Your position, required only to accept
    <select name="ans-{e(f['id'])}" aria-describedby="err-{e(f['id'])}"><option value="">Choose a position…</option>{options}</select>
  </label>
  <p class="field-error" id="err-{e(f['id'])}" hidden></p>
  <details class="risk-context"><summary>Add an optional note</summary><label class="ans">Note
    <input type="text" name="note-{e(f['id'])}" data-note-for="{e(f['id'])}" placeholder="Optional context; leave blank if none">
  </label></details>
</article>""")
    if not items:
        return ""
    return f"""
<section class="sec" id="refused">
  <h3>Risk decisions</h3>

  <div class="stack">{''.join(items)}</div>
</section>"""


def render_unknowns(r):
    items = "".join(
        f'<li id="unknown-{e(u["id"])}" data-unknown="{e(u["id"])}">'
        f'<label><input type="checkbox" name="unk-{e(u["id"])}" aria-describedby="err-{e(u["id"])}"> <b>{e(u["id"])}</b> {e(u["text"])}'
        f'<span class="field-error" id="err-{e(u["id"])}" hidden></span></label></li>'
        for u in r.get("unknowns", []))
    if not items:
        return ""
    return f"""
<section class="sec" id="unknowns">
  <h3>Limits to acknowledge</h3>

  <ul class="unknowns">{items}</ul>
</section>"""


def render_classifications(r):
    claims = r["claims"]
    counts = {s: sum(1 for c in claims if c["status"] == s) for s in STATUS_ORDER}
    bar = stacked([(f"s-{s}", STATUS[s][0], counts[s]) for s in STATUS_ORDER], "Claims by evidence classification")
    rows = "".join(
        f'<tr><td><a class="cl" href="#claim-{e(c["id"])}" data-open="claim-{e(c["id"])}">{mono(c["id"])}</a></td>'
        f'<td>{chip(c["status"])}</td><td>{e(c["statusReason"])}</td></tr>'
        for c in claims)
    return f"""
<section class="sec" id="classifications">
  <h2>How reliable are the AI's claims?</h2>
  <p class="lede">These are <b>evidence-linkage classifications</b>, not a trust score or a hallucination count. <b>Test-backed</b> means a named test ran with the expected outcome; relevance is not proven. <b>Contradicted</b> means a linked outcome conflicted with its configured expectation. <b>Unsupported</b> means cited executed evidence is absent or insufficient, so the claim is unproven, not proven false. <b>Source only</b> means the cited range resolves; runtime behaviour is not established.</p>
  {bar}
  <div class="tablewrap"><table class="grid">
    <thead><tr><th>ID</th><th>Classification</th><th>Exact engine reason</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>"""


def decision_template(r):
    lines = ["/receipt accept [your reason, including residual risks]",
             "Head: " + r["subject"]["headSha"]]
    for x in r.get("refusals", []):
        choices = " | ".join(p["id"] for p in x.get("positions", [])) or "no positions recorded"
        lines.append(f'{x["id"]}: [{choices}]')
    for x in r.get("outOfRequirement", []):
        lines.append(f'{x["id"]}: [{ " | ".join(decision.FINDING_POSITIONS) }]')
    for x in r.get("unknowns", []):
        lines.append(f'{x["id"]}: [acknowledged]')
    return "\n".join(lines)


def render_decision(r):
    pr = receipt_pr(r)
    d = r["decision"]
    if d["status"] == "pending":
        signed = ""
    else:
        positions = "".join(
            f'<li>{mono(p["refusalId"])}: {mono(p["positionId"])}'
            + (f' — {e(p["note"])}' if p.get("note") else "") + '</li>'
            for p in d.get("refusalPositions", []))
        findings = "".join(
            f'<li>{mono(p["findingId"])}: {mono(p["positionId"])}</li>'
            for p in d.get("findingPositions", []))
        acknowledgements = ", ".join(d.get("acceptedUnknownRefs", []))
        extra = ""
        if positions or findings or acknowledgements:
            extra = ('<div class="recorded"><b>Recorded positions</b><ul class="plain">'
                     + positions + findings + '</ul>'
                     + (f'<p>Acknowledged unknowns: {e(acknowledgements)}</p>' if acknowledgements else '')
                     + '</div>')
        signed = (f'<div class="signedbox"><p><b>{e(decision_label(r))}</b> · {e(d["signedAt"])}'
                  f'<br>{e(d["reason"])}</p>{extra}' + (f'<a href="{e(d["sourceCommentUrl"])}">Original GitHub decision</a>' if d.get('sourceCommentUrl') else '') + '</div>')
    template = decision_template(r)
    return f"""
<form class="decision" id="decision" autocomplete="off">
  {signed}
  <h2>What is your decision?</h2>
  <p>Anyone with a GitHub account can record a demo outcome. No code is merged.</p>
  <div class="dstate" id="dstate" aria-live="polite">No decision selected.</div>
  <button type="button" class="linkish" id="first-error" hidden>Go to the first field that needs attention</button>
  <div class="drow">
    <fieldset class="seg3 outcomes" aria-describedby="err-outcome"><legend>Outcome</legend>
      <label><input type="radio" name="outcome" value="accept"> Accept listed risks</label>
      <label><input type="radio" name="outcome" value="changes"> Request changes</label>
      <label><input type="radio" name="outcome" value="escalate"> Escalate for code/domain review</label>
      <p class="field-error" id="err-outcome" hidden></p>
    </fieldset>
  </div>
  <div class="risk-review">
    <h2>What needs your judgement?</h2>
    {render_refusals(r)}{render_findings(r)}{render_unknowns(r)}
  </div>
  <div class="drow reason-row">
    <label class="grow">Reason<input name="reason" type="text" aria-describedby="err-reason" placeholder="Your reason in your own words">
      <span class="field-error" id="err-reason" hidden></span>
    </label>
    <button type="submit" class="primary" id="copy-comment" disabled>Copy decision draft</button>
    <a class="btn" href="{e(pr.get('url', '#'))}">Open PR #{pr.get('number', '—')}</a>
    <span>Status: {e(status_label(r))}</span>
  </div>
  <details><summary>Comment to paste in the PR</summary><pre id="comment-preview">{e(template)}</pre></details>
  <div class="dfoot">Copy → open PR → post with your GitHub account. Only a comment you post in GitHub can be applied as a decision. Reviewed head: <code>{e(short(r['subject']['headSha']))}</code>. A new push needs fresh evidence. Escalation stays pending owner judgement.</div>
</form>"""


def code_html(text, language="csharp"):
    lexer = {"csharp": CSharpLexer, "markdown": MarkdownLexer}.get(language, TextLexer)
    return highlight(text, lexer(), HtmlFormatter(nowrap=True)).rstrip("\n")


def render_patch(patch, language="text"):
    """Escape literal git output; never render model-written source as code evidence."""
    lines = []
    current_language = language
    for line in patch.splitlines():
        if line.startswith('+++ b/'):
            current_language = 'csharp' if line.endswith('.cs') else 'markdown' if line.endswith('.md') else 'text'
        if 'https://github.com/MessagePack-CSharp/MessagePack-CSharp/issues/' in line:
            line = line.split('See https://')[0] + 'See R2283 (local demo requirement; source URL omitted in display).'
        cls = 'add' if line.startswith('+') and not line.startswith('+++') else 'remove' if line.startswith('-') and not line.startswith('---') else 'context'
        lines.append(f'<span class="diffline {cls}">{code_html(line, current_language)}</span>')
    return '<pre class="diff" tabindex="0" aria-label="Recorded code diff">' + '\n'.join(lines) + '</pre>'


def load_snapshot(r):
    path = ROOT / 'walkthrough/data/r2283-code.json'
    if not path.exists():
        return None
    try:
        snapshot = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if any(snapshot.get(k) != r['subject'][k] for k in ('baseSha', 'headSha')):
        return None
    return snapshot


def render_source_optional(r):
    snapshot = load_snapshot(r)
    if snapshot is None:
        return f"""
<section class="sec" id="source">
  <h2>Optional implementation evidence</h2>
  <div class="card unavailable">
    <p><b>Optional implementation evidence unavailable for this receipt.</b></p>
    <p>No source snapshot matches the recorded base and head. The decision brief, classifications, checks, risks and unknowns above are unaffected; stale source is never shown as current.</p>
  </div>
</section>"""
    source = snapshot['files'][0]
    excerpt = snapshot.get('focusExcerpt')
    numbered = ""
    if excerpt:
        numbered = ('<div class="code-heading"><b>' + e(source['path'].rsplit('/', 1)[-1])
                    + ' · lines ' + str(excerpt['startLine']) + '–' + str(excerpt['endLine'])
                    + '</b><span>C# · Exact head source excerpt</span></div>'
                    + '<pre class="diff" tabindex="0" aria-label="Optional source excerpt">'
                    + '\n'.join(f'<span class="source-line"><span class="line-number">{i}</span>{code_html(line)}</span>' for i, line in enumerate(excerpt['text'].splitlines(), excerpt['startLine']))
                    + '</pre>')
    files = ''.join(f'<details class="code-detail"><summary>{e(f["path"])}</summary>{render_patch(f["patch"])}</details>'
                    for f in snapshot['files'])
    return f"""
<section class="sec" id="source">
  <h2>Optional implementation evidence</h2>
  <p class="lede">Source and diffs are corroboration, not a required step. They are shown only because this snapshot matches the recorded base and head.</p>
  <details class="code-detail"><summary>Open the recorded source and diffs (optional)</summary>
    {numbered}
    {files}
    <details><summary>Complete patch</summary>
      <p class="muted small">Source issue URLs in test comments are replaced by the local requirement label for this display. Executable code is unchanged.</p>{render_patch(snapshot['fullPatch'])}
      <details><summary>Sample source license and original authorship</summary><pre class="license-text">{e(snapshot['license'])}</pre></details>
    </details>
    <p class="muted small">{e(snapshot['attribution'])} Code is bound to head {e(short(snapshot['headSha']))}. Checks are recorded runs, not newly executed here.</p>
  </details>
</section>"""


def render_receipt(r):
    return f"""
<section class="view" id="view-receipt">
  {render_header(r)}
  <section class="sec" id="overview">
    <h2>What changed?</h2>
    <p>The patch targets a generator crash involving a generic value type from another assembly.</p>
    <h2>What supports it?</h2>
    <p><b>The regression tests fail before the patch and pass after it.</b> Other consumer scenarios remain unverified.</p>
    <a href="#evidence" data-open="evidence">Inspect supporting evidence</a>
  </section>
  {render_decision(r)}
  <details class="audit" id="evidence"><summary>Supporting evidence · tests, claims and explanations</summary>
    {render_brief(r)}{render_classifications(r)}{render_checks(r)}{render_fail_then_pass(r)}
  </details>
  {render_source_optional(r)}
  <details class="audit"><summary>Full receipt · routing and traceability</summary>
    <p class="muted">A test-backed claim is not proof of semantic relevance or complete coverage.</p>
    {render_rail(r)}{render_focus(r)}{render_coverage(r)}{render_claims(r)}
  </details>
</section>"""


# ---------------------------------------------------------------- queue

FLOW = [
    ("Agent opens a pull request", "A change arrives with a requirement ID.", "built", "Four demo PRs, each based on the AI commit’s parent."),
    ("Harness runs the checks", "Only the harness writes check results.", "partial", "Results recorded from scripts in evidence/. No runner yet."),
    ("Model proposes, engine decides", "DeepSeek proposes claims; the engine computes each status.", "built", "Built, run on R2283."),
    ("Rules route attention", "Named rules set the depth and the places to read.", "built", "Built."),
    ("A named human decides", "Accept listed risks, request changes, or escalate, bound to the head SHA.", "built", "CLI reads the human’s PR comment and sets a status for that head. Run manually; no event automation."),
]
FLOW_LABEL = {"built": "Built", "partial": "Partly built", "manual": "Not built"}


def render_queue(triage, r):
    tiers = ["light", "standard", "full_read"]
    t_before = {t: sum(1 for x in triage if x["tier"] == t) for t in tiers}
    after = {x["id"]: x["tier"] for x in triage}
    after[r["requirement"]["id"]] = r["routing"]["tier"]
    t_after = {t: sum(1 for v in after.values() if v == t) for t in tiers}
    n = len(triage)
    bars = (
        '<div class="barlabel">Triage, before any AI call</div>' +
        stacked([(f"t-{t}", TIER[t], t_before[t]) for t in tiers], "Triage routing") +
        '<div class="barlabel">After evidence (only R2283 has a receipt)</div>' +
        stacked([(f"t-{t}", TIER[t], t_after[t]) for t in tiers], "Routing after evidence")
    )
    rows = []
    for x in triage:
        is_full = x["id"] == r["requirement"]["id"]
        after_tier = after[x["id"]]
        changed = after_tier != x["tier"]
        state = (f'<a class="primarylink" href="#receipt">Receipt built, {e(r["decision"]["status"].replace("_", " "))}</a>' if is_full
                 else '<span class="muted">Triage only</span>')
        pr = receipt_pr({"requirement": {"id": x["id"]}})
        owner = r["decision"].get("owner", "Not assigned") if is_full else "Not assigned"
        pr_cell = f'<a href="{e(pr.get("url", "#"))}">PR #{pr.get("number", "—")}</a><div class="muted small">{e(pr.get("status", "pending"))}</div>'
        route = tier_badge(x["tier"]) + (f'<span class="to">{icon("arrow")}</span>{tier_badge(after_tier)}' if changed else "")
        lines = x["lines"]
        diff = f"{lines['source']} source · {lines['tests']} tests · {lines['docs']} docs" + (f" · {lines['generated']} generated" if lines["generated"] else "")
        rows.append(f"""
<tr>
  <td><code>{e(local_requirement_id(x['id']))}</code><div class="muted small"><code>{e(x['head'])}</code></div></td>
  <td><b>{e(x['title'])}</b><div class="muted small">Requirement: {e(x['quality'].replace('_', ' '))}. {e(x['note'])}</div></td>
  <td class="nowrap">{route}</td>
  <td>{e('; '.join(x['reasons']))}<div class="muted small">{e(diff)} lines</div></td>
  <td>{state}</td>
  <td>{pr_cell}</td>
  <td><span class="muted">{e(owner)}</span></td>
</tr>""")
    flow = "".join(
        f'<li class="step st-{st}"><div class="num">{i + 1}</div><div><b>{e(t)}</b><p>{e(d)}</p><span class="tag">{e(FLOW_LABEL[st])}</span> <span class="muted small">{e(note)}</span></div></li>'
        for i, (t, d, st, note) in enumerate(FLOW))
    return f"""
<section class="view" id="view-queue" hidden>
  <div class="hero">
    <div class="overline">HackJunction 2026 · Earned trust in AI code</div>
    <h1>Do not ask humans to trust the AI reviewer. Ask them to trust evidence they can check.</h1>
    <p class="lede big">For each agent-written change, the AI reviewer produces a <b>receipt</b>: what was claimed, what actually ran, what the AI refused to decide, and how deeply a human should look. A named engineer decides. The decision is bound to the exact head commit.</p>
    <div class="cta"><a class="btn primary" href="#receipt">Open the R2283 receipt</a><button type="button" class="btn" data-open-dialog="principles">Principles, trade-offs and limits</button></div>
  </div>
  <section class="sec">
    <h2>The queue</h2>
    <p class="lede">Four sample agent-written changes in our demo environment. Review Receipt is our HackJunction 2026 project; the supplied code is demo material. Triage uses only the requirement quality and the diff shape. A receipt can raise a tier once evidence is in: R2283 looked light, then a contradicted claim and two open questions moved it to standard.</p>
    <div class="card">{bars}
      <p class="muted small">{t_before['full_read']} of {n} changes need a full read at triage. Thresholds are untuned guesses (the 400-line limit especially).</p>
    </div>
    <div class="tablewrap"><table class="grid queue">
      <thead><tr><th>Change</th><th>Requirement</th><th>Review depth</th><th>Why</th><th>State</th><th>PR / status</th><th>Owner</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table></div>
  </section>
  <section class="sec">
    <h2>Where this sits in a pull-request flow</h2>
    <p class="lede">The receipt replaces “read the whole diff” with “check the evidence, then decide”. This is what is built today.</p>
    <ol class="flow">{flow}</ol>
  </section>
</section>"""


# ---------------------------------------------------------------- measurement

def render_measurement(model, triage, r):
    claims = model["claims"]
    inj = [c for c in claims if str(c.get("modelNote", "")).startswith("INJECTED")]
    real = [c for c in claims if c not in inj]

    def counts(cs):
        return [(f"s-{s}", STATUS[s][0], sum(1 for c in cs if c["status"] == s)) for s in STATUS_ORDER]

    real_ver = sum(1 for c in real if c["status"] == "verified")
    inj_ok = sum(1 for c in inj if c["status"] != "verified")
    rows = []
    for c in claims:
        tag = '<span class="tag warn">Injected wrong claim</span>' if c in inj else ""
        rows.append(f'<tr><td><code>{e(c["id"])}</code></td><td>{e(c["text"])} {tag}</td><td>{chip(c["status"])}</td></tr>')
    n = len(triage)
    full = sum(1 for x in triage if x["tier"] == "full_read")
    return f"""
<section class="view" id="view-measurement" hidden>
  <div class="hero compact">
    <div class="overline">Evidence and lessons</div>
    <h1>What we can show today, what the page records, and what is still a plan</h1>
    <p class="lede big">Review time may fall only if reverts and incidents do not rise. Track both together; if incidents rise while review time falls, tighten routing. Nothing below is a trust score, and every figure is labelled with how it was obtained.</p>
  </div>

  <section class="sec">
    <h2>Observed failures → design decisions</h2>
    <ul><li>A passing suite was treated as proof of a specific claim → require named tests; still disclose relevance limits.</li>
    <li>An expected comparison failure looked like a broken build → separate diagnostic probes from merge gates.</li>
    <li>Real citations can support an incorrect explanation → expose exact code and keep semantic judgment human.</li>
    <li>The receipt became a wall of text → focus on the consequential change and expand the audit trail on demand.</li></ul>
    <p><a href="https://github.com/nicholsss/junction/blob/main/docs/DECISIONS.md">Read the short decision log</a> · No valid human acceptance recorded; no review-time savings measured.</p>
  </section>
  <section class="sec">
    <h2>Measured on one change</h2>
    <div class="twocol">
      <div class="card">
        <h3>Do the model’s claims hold up?</h3>
        <p class="muted">A model run on R2283 ({e(model['provenance']['model'])}), with five wrong claims added on purpose. Statuses are computed by the engine.</p>
        <div class="barlabel">Real claims proposed by the model ({len(real)})</div>
        {stacked(counts(real), 'Real claims by status')}
        <div class="barlabel">Injected wrong claims ({len(inj)})</div>
        {stacked(counts(inj), 'Injected claims by status')}
        <p class="big-n"><b>{inj_ok} of {len(inj)}</b> injected claims were not verified. <b>{real_ver} of {len(real)}</b> real claims were verified.</p>
        <p class="muted small">One change, one model, one run. This shows the mechanism works, not that it generalises. One real claim was marked contradicted only because it also cited the probe check.</p>
      </div>
      <div class="card">
        <h3>What share goes to a human?</h3>
        <p class="muted">Triage tier of the four supplied changes, from requirement quality and diff shape only.</p>
        {stacked([(f"t-{t}", TIER[t], sum(1 for x in triage if x['tier'] == t)) for t in ['light', 'standard', 'full_read']], 'Triage routing')}
        <p class="big-n"><b>{full} of {n}</b> need a full read; every change still needs a named human decision.</p>
        <p class="muted small">Four changes is a demonstration, not a rate. The thresholds are guesses until tuned on more changes.</p>
      </div>
    </div>
    <details class="plainbox"><summary>All {len(claims)} claims from the model run</summary>
      <div class="tablewrap"><table class="grid"><thead><tr><th>ID</th><th>Claim</th><th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
    </details>
  </section>

  <section class="sec">
    <h2>Draft activity in this page</h2>
    <p class="lede">These counters describe unsaved draft activity in the open page. They reset on reload and are not pilot results or signed decisions.</p>
    <div class="metrics">
      <div class="card metric"><div class="overline">Time to decision</div><div class="num" id="m-time">None recorded</div><p class="muted small">Not measured. Drafting a PR comment is not a signed decision.</p></div>
      <div class="card metric"><div class="overline">Refusal and finding positions</div><div class="num" id="m-answers">0 chosen</div><p class="muted small">Draft selections in this page. They are not measurements or a signed decision.</p></div>
      <div class="card metric"><div class="overline">Unknowns acknowledged</div><div class="num" id="m-unknowns">0 of {len(r.get('unknowns', []))}</div><p class="muted small">Draft acknowledgements. Only a comment posted by the human in GitHub can become a decision.</p></div>
    </div>
  </section>

  <section class="sec">
    <h2>The plan, not yet measured</h2>
    <div class="tablewrap"><table class="grid">
      <thead><tr><th>Question</th><th>Measure</th><th>State</th></tr></thead>
      <tbody>
        <tr><td>Does it save review time?</td><td>Time to decision with a receipt versus a plain diff, same changes, pairs of engineers.</td><td><span class="chip s-notrun">{icon('dashed')}Not measured</span></td></tr>
        <tr><td>Does it catch real defects?</td><td>Planted defects found with a receipt versus without. Needs a seeded-defect set.</td><td><span class="chip s-notrun">{icon('dashed')}Not measured</span></td></tr>
        <tr><td>Does it mislead?</td><td>False reassurance: reviewers who accept a defective change because the receipt looked clean.</td><td><span class="chip s-notrun">{icon('dashed')}Not measured</span></td></tr>
        <tr><td>Time to merge</td><td>Open to merge, split into waiting and human time. Needs a real pull-request flow.</td><td><span class="chip s-notrun">{icon('dashed')}Not measured</span></td></tr>
        <tr><td>Is routing right?</td><td>Agreement between tier and an expert’s view of the depth needed.</td><td><span class="chip s-notrun">{icon('dashed')}Not measured</span></td></tr>
        <tr><td>Do reverts and incidents rise as review time falls?</td><td>Reverts, hotfixes and incidents on accepted changes, compared with review time.</td><td><span class="chip s-notrun">{icon('dashed')}Needs months</span></td></tr>
      </tbody>
    </table></div>
    <div class="note">{icon('info')}<span><b>Proposed first experiment.</b> Six agent-written changes, three with a planted defect, reviewed by pairs of engineers with and without a receipt. Record time, defects caught and false reassurance.</span></div>
  </section>
</section>"""


# ---------------------------------------------------------------- dialog

PRINCIPLES = [
    ("Three kinds of statement, never mixed.", "Executed checks (written only by the harness), AI claims (status computed), and AI refusals (questions for the human)."),
    ("A model’s prose cannot become evidence.", "The model never sets a status. The engine re-resolves each citation and computes it."),
    ("A claim is verified only through a named test that ran.", "A whole-suite pass cannot verify a specific claim; that link goes to a human."),
    ("Failed, skipped and not-run checks stay visible.", "None becomes a pass."),
    ("Route attention by named rules.", "No trust score. Each review depth lists the rules that fired and what was observed."),
    ("Decisions are bound to a commit.", "A different head SHA makes the receipt stale."),
    ("Ownership stays human.", "No automatic approval or merge."),
]
TRADEOFFS = [
    "Fewer verified claims, more human attention. That is deliberate.",
    "Rules over a score: rules can be argued with and tuned. The cost is that thresholds are guesses until measured.",
    "Deterministic engine, advisory model: the model adds coverage but its claims are only as good as its choice of claim.",
    "Probes versus gates: a mislabelled probe could hide a real failure.",
]
LIMITS = [
    "Relevance is not proven: the engine checks that a named test exists and ran, not that it tests what the claim says.",
    "A citation proves the lines exist, not that they say what the claim says, so code claims reach “source only” at most.",
    "One repository, one machine, .NET 8. The two-project repro from the issue was not run.",
    "The crash-only comparison is a local hand-applied approximation of a reference fix; it is not a run of that reference patch.",
    "GitHub integration runs manually. A pull_request Action and branch protection requiring review-receipt are not built. The page is a snapshot; new pushes have no successful review-receipt status, and the CLI detects stale evidence when run.",
    "Bot and human share one login in a single-account demo; prefer a teammate’s own account. No signer has been assigned.",
    "The 400-line threshold is untuned. Nothing here shows long-term reliability.",
]


def render_dialog():
    p = "".join(f"<li><b>{e(a)}</b> {e(b)}</li>" for a, b in PRINCIPLES)
    t = "".join(f"<li>{e(x)}</li>" for x in TRADEOFFS)
    l = "".join(f"<li>{e(x)}</li>" for x in LIMITS)
    return f"""
<dialog id="principles" class="sheet">
  <div class="sheethead"><h2>Principles, trade-offs and limits</h2><button type="button" class="btn" data-close-dialog>Close</button></div>
  <p><b>Our recommendation:</b> automate repeatable checks and focus human judgment on consequential uncertainty.</p>
  <p><b>Risk:</b> escalate scope changes and missing evidence. <b>Hallucination:</b> check citations and executed tests; semantic mistakes remain possible. <b>Transparency:</b> show source, provenance and gaps. <b>Confidence:</b> scope each statement rather than give a score. <b>Quality:</b> track misses and outcomes alongside time saved.</p>
  <h3>Seven principles</h3><ol>{p}</ol>
  <h3>Trade-offs</h3><ul>{t}</ul>
  <h3>Limits</h3><ul>{l}</ul>
</dialog>"""


# ---------------------------------------------------------------- shell

CSS = r"""
:root{
  --bg:#F7F8FA;--card:#FFFFFF;--line:#E3E6EB;--text:#14181F;--muted:#5B6472;--accent:#2F4BCB;--accent-tint:#EBEFFD;
  --ok:#00785A;--ok-bg:#E6F4EF;--bad:#C23B00;--bad-bg:#FBEAE2;--warn:#8A5A00;--warn-bg:#FFF3D6;
  --link:#0066A8;--link-bg:#E4F0FA;--src:#4F5866;--src-bg:#EEF0F3;
  --t-light:#D6E0FF;--t-standard:#8FA6F2;--t-full:#2F4BCB;
  --radius:8px;--shadow:0 1px 2px rgba(20,24,31,.06),0 2px 8px rgba(20,24,31,.04);
  --sans:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:76px}
body{margin:0;background:var(--bg);color:var(--text);font:400 16px/1.55 var(--sans);-webkit-font-smoothing:antialiased}
code,.mono{font-family:var(--mono);font-size:13px;font-variant-numeric:tabular-nums}
code{background:var(--src-bg);border-radius:4px;padding:1px 5px;overflow-wrap:anywhere}
h1{overflow-wrap:anywhere;font-size:28px;line-height:1.2;margin:.2em 0 .4em;font-weight:600;letter-spacing:-.01em}
h2{font-size:20px;margin:0 0 .3em;font-weight:600}
h3{font-size:16px;margin:0 0 .4em;font-weight:600}
p{margin:.4em 0}
a{color:var(--accent)}
.muted{color:var(--muted)} .small{font-size:12px} .nowrap{white-space:nowrap}
.overline{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:4px}
.ic{width:14px;height:14px;flex:none}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}

/* shell */
.top{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.top .in{max-width:1120px;margin:0 auto;padding:0 16px;height:56px;display:flex;align-items:center;gap:20px}
.brand{font-weight:600;display:flex;gap:8px;align-items:center;white-space:nowrap}
.brand i{width:10px;height:10px;border-radius:2px;background:var(--accent);display:inline-block}
nav{display:flex;gap:4px;flex:1;min-width:0;overflow-x:auto}
#open-principles{flex:none}
nav a{white-space:nowrap;padding:8px 12px;border-radius:6px;color:var(--muted);text-decoration:none;font-weight:500;font-size:14px}
nav a[aria-current=page]{color:var(--accent);background:var(--accent-tint)}
nav a:hover{color:var(--text)}
.wrap{max-width:1120px;margin:0 auto;padding:24px 16px 120px}
.btn{font:500 14px var(--sans);padding:8px 14px;border:1px solid var(--line);background:#fff;border-radius:6px;cursor:pointer;color:var(--text);text-decoration:none;display:inline-block}
.btn:hover{border-color:#c9ced6}
.btn.primary,button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.primary:disabled{background:#B7BFE3;border-color:#B7BFE3;cursor:not-allowed}
.primarylink{font-weight:500}

/* hero */
.hero{padding:28px 0 8px}
.hero h1{font-size:34px;max-width:860px}
.hero.compact h1{font-size:28px;max-width:820px}
.lede{color:var(--muted);max-width:760px;margin:.2em 0 1em}
.lede.big{font-size:18px;color:#2a313c;line-height:1.55}
.cta{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}
.sec{margin:36px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:16px;box-shadow:var(--shadow)}
.stack{display:grid;gap:12px}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.banner{margin-top:12px;padding:10px 12px;border-radius:6px;background:var(--ok-bg);color:#064f3c;font-size:14px}
.banner.stale{background:var(--bad-bg);color:#7a2500}
.note{display:flex;gap:10px;margin-top:14px;padding:12px 14px;background:var(--accent-tint);border-radius:var(--radius);font-size:14px;color:#1b2a78;align-items:flex-start}
.note .ic{margin-top:4px;width:16px;height:16px}
.plainbox{margin-top:12px}.plainbox summary{cursor:pointer;color:var(--accent);font-weight:500}

/* tables */
.tablewrap{overflow-x:auto;margin-top:12px;border:1px solid var(--line);border-radius:var(--radius);background:#fff;box-shadow:var(--shadow)}
table.grid{border-collapse:collapse;width:100%;font-size:14px}
.grid th{text-align:left;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);padding:10px 12px;border-bottom:1px solid var(--line);background:#FBFBFC;font-weight:600}
.grid td{padding:12px;border-bottom:1px solid var(--line);vertical-align:top}
.grid tr:last-child td{border-bottom:0}
.grid td:first-child code{white-space:nowrap}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.cl{display:inline-flex;gap:6px;align-items:center;text-decoration:none}
.origin{margin-left:8px;font-size:11px;padding:1px 6px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
.o-stated{color:var(--ok);border-color:#b7dccd}
.queue td:first-child code{white-space:nowrap}
.queue td:nth-child(3) .tier{margin-right:2px}
.to{display:inline-flex;vertical-align:middle;margin:0 4px;color:var(--muted)}

/* chips and tiers */
.chip{display:inline-flex;align-items:center;gap:5px;font-size:12px;font-weight:600;padding:3px 9px 3px 7px;border-radius:99px;white-space:nowrap}
.s-verified{background:var(--ok-bg);color:var(--ok)}
.s-contradicted{background:var(--bad-bg);color:var(--bad)}
.s-unsupported{background:var(--warn-bg);color:var(--warn)}
.s-needs_link_review{background:var(--link-bg);color:var(--link)}
.s-source_only{background:var(--src-bg);color:var(--src)}
.s-notrun{background:#fff;color:var(--muted);border:1px dashed #AEB5C0}
.tier{display:inline-block;font-size:12px;font-weight:600;padding:3px 10px;border-radius:6px}
.t-light{background:var(--t-light);color:#16206a}
.t-standard{background:var(--t-standard);color:#0c1650}
.t-full_read{background:var(--t-full);color:#fff}
.tier.big{font-size:18px;padding:6px 14px;margin:2px 0 6px}
.tag{display:inline-flex;gap:5px;align-items:center;font-size:12px;padding:2px 8px;border-radius:99px;background:var(--src-bg);color:var(--src);font-weight:500}
.tag.warn{background:var(--warn-bg);color:var(--warn)} .tag.ask{background:var(--link-bg);color:var(--link)}
.tag[data-state=decided]{background:var(--ok-bg);color:var(--ok)} .tag[data-state=stale]{background:var(--bad-bg);color:var(--bad)}
.mini{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:5px}

/* stacked bar */
.bar{display:flex;height:30px;border-radius:6px;overflow:hidden;gap:2px;margin:6px 0}
.seg{display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;min-width:26px}
.seg.t-light,.sw.t-light{background:var(--t-light);color:#16206a}
.seg.t-standard,.sw.t-standard{background:var(--t-standard);color:#0c1650}
.seg.t-full_read,.sw.t-full_read{background:var(--t-full);color:#fff}
.seg.s-verified,.sw.s-verified{background:var(--ok);color:#fff}
.seg.s-contradicted,.sw.s-contradicted{background:var(--bad);color:#fff}
.seg.s-unsupported,.sw.s-unsupported{background:var(--warn);color:#fff}
.seg.s-needs_link_review,.sw.s-needs_link_review{background:var(--link);color:#fff}
.seg.s-source_only,.sw.s-source_only{background:var(--src);color:#fff}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:10px}
.lg{display:inline-flex;align-items:center;gap:6px}
.sw{width:10px;height:10px;border-radius:2px;display:inline-block}
.barlabel{font-size:13px;font-weight:600;margin-top:10px}
.big-n{font-size:15px;margin-top:10px}

/* receipt layout */
.rhead{padding:8px 0 4px}
.meta{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:14px}
.prov{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.rgrid{display:grid;grid-template-columns:280px minmax(0,1fr);gap:28px;align-items:start;margin-top:8px}
.rail{position:sticky;top:76px;display:grid;gap:12px;max-height:calc(100vh - 250px);overflow:auto}
.rules{list-style:none;padding:0;margin:4px 0 0;display:grid;gap:8px}
.rules li{font-size:13px;border-left:3px solid var(--t-standard);padding-left:10px}
.rule{display:block;font-weight:500}.obs{display:block;color:var(--muted);font-family:var(--mono);font-size:12px}
.limits ul{padding-left:18px;margin:4px 0;font-size:13px;color:#2a313c}
.main .sec:first-child{margin-top:12px}
.focus{list-style:none;padding:0;margin:8px 0;display:grid;gap:8px}
.path{overflow-wrap:anywhere;margin-top:4px}
.focus li{min-width:0;overflow-wrap:anywhere;display:grid;grid-template-columns:minmax(0,230px) minmax(0,1fr);gap:12px;background:#fff;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:var(--radius);padding:10px 12px;font-size:14px}
.where{background:var(--accent-tint);color:#1b2a78}

/* claims */
.claims{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;margin-top:8px}
.claim{min-width:0;overflow-wrap:anywhere;background:#fff;border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow)}
.claim summary{list-style:none;display:grid;grid-template-columns:auto auto minmax(0,1fr) auto;gap:10px;align-items:center;padding:12px;cursor:pointer}
.claim summary::-webkit-details-marker{display:none}
.claim[open] summary{border-bottom:1px solid var(--line)}
.ctext{font-size:15px}.kind{font-size:12px;color:var(--muted)}
.claimbody{padding:14px 12px}
.chain{list-style:none;display:grid;gap:0;padding:0;margin:0 0 12px;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.chain>li{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px;padding:10px 12px;font-size:13px;background:var(--bg);align-items:start}
.chain>li+li{border-top:1px solid var(--line)}
.chain>li>.overline{margin:2px 0 0}
.chain p{margin:0}
.plain,.tests{list-style:none;padding:0;margin:0;display:grid;gap:6px}
.minis{display:flex;gap:4px;flex-wrap:wrap;margin-top:4px}
.why{font-size:14px;margin-top:8px}.why p{margin:2px 0;color:#2a313c}

/* ftp */
.ftp td,.ftp th{text-align:left}
.ftp th{white-space:nowrap}.ftp td:first-child{width:46%}.ftp td:first-child code{white-space:normal}

/* checks */
.checks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:8px}
.chead{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.check h3{font-size:15px}
.kv{display:grid;grid-template-columns:70px 1fr;gap:8px;font-size:13px;margin-top:6px}
.kv>span:first-child{color:var(--muted)}
.kv code{font-size:12px}

/* findings and refusals */
textarea,input[type=text]{font:inherit;font-size:14px;border:1px solid #C9CED6;border-radius:6px;padding:8px 10px;width:100%;background:#fff;color:var(--text)}
textarea{resize:vertical}
.ans{display:block;margin-top:10px;font-size:13px;font-weight:500}
.ans textarea{margin-top:4px}
fieldset{border:0;margin:0;padding:0}
legend{font-size:12px;color:var(--muted);padding:0;margin-bottom:4px;font-weight:500}
.seg3{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:10px}
.seg3 legend{width:100%}
.seg3 label{display:inline-flex;gap:6px;align-items:center;font-size:14px;cursor:pointer}
.refusal.done{border-color:#b7dccd}.finding.done{border-color:#b7dccd}
.field-error{color:var(--bad);font-size:13px;line-height:1.45;margin:4px 0 0;font-weight:500}
select[aria-invalid=true],input[aria-invalid=true]{border-color:var(--bad);box-shadow:0 0 0 1px var(--bad)}
.refusal.invalid,.finding.invalid{border-color:var(--bad)}
.seg3.invalid legend{color:var(--bad)}
.unknowns{list-style:none;padding:0;margin:8px 0 0;display:grid;gap:8px}
.unknowns label{display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap}
.unknowns .field-error{flex-basis:100%;margin-left:24px}
.linkish{background:none;border:0;padding:0;margin:0 0 8px;font:500 13px var(--sans);color:var(--accent);text-decoration:underline;cursor:pointer}
.card,.sec{scroll-margin-top:84px}

/* flow */
.flow{list-style:none;padding:0;margin:12px 0 0;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}
.step{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:12px;display:grid;gap:6px;font-size:13px;box-shadow:var(--shadow)}
.step .num{width:22px;height:22px;border-radius:50%;background:var(--accent-tint);color:var(--accent);font-weight:600;display:grid;place-items:center;font-size:12px}
.step p{margin:2px 0 8px;color:var(--muted)}
.st-manual{border-style:dashed}

/* measurement */
.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.metric .num{font-size:22px;font-weight:600;margin:4px 0;font-variant-numeric:tabular-nums}

/* decision bar */
.decision pre{white-space:pre-wrap;overflow-wrap:anywhere}
.decision{position:sticky;bottom:0;z-index:15;margin:32px -16px 0;background:#fff;border-top:1px solid var(--line);box-shadow:0 -4px 16px rgba(20,24,31,.08);padding:8px 16px}
.dstate{font-size:13px;color:var(--muted);margin-bottom:8px}
.dstate.ready{color:var(--ok);font-weight:500}
.drow{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap}
.drow label{font-size:12px;font-weight:500;color:var(--muted);display:grid;gap:4px;min-width:170px}
.drow .grow{flex:1;min-width:220px}
.drow fieldset.seg3{margin:0}
.drow fieldset.seg3 label{display:inline-flex;color:var(--text);font-size:14px;font-weight:400;min-width:0}
.drow button{padding:9px 16px;border-radius:6px;border:1px solid var(--accent);font:500 14px var(--sans);cursor:pointer}
.dfoot{font-size:12px;color:var(--muted);margin-top:8px}
dialog{border:1px solid var(--line);border-radius:12px;padding:20px;max-width:560px;box-shadow:0 12px 40px rgba(20,24,31,.25)}
dialog::backdrop{background:rgba(20,24,31,.4)}
.dbtns{display:flex;gap:8px;justify-content:flex-end;margin-top:16px}
.dbtns button{font:500 14px var(--sans);padding:8px 14px;border-radius:6px;border:1px solid var(--line);background:#fff;cursor:pointer}
.sheet{max-width:720px;width:calc(100% - 32px);max-height:85vh;overflow:auto}
.sheethead{display:flex;justify-content:space-between;align-items:center;gap:12px}
.sheet ol,.sheet ul{padding-left:20px;font-size:14px}.sheet li{margin:6px 0}
.foot{margin-top:40px;color:var(--muted);font-size:12px}

.js .view[hidden]{display:none}
@media (max-width:900px){
  .rgrid{grid-template-columns:minmax(0,1fr)}.rail{position:static;max-height:none;overflow:visible}
  .decision{position:static;margin:24px 0 0;border:1px solid var(--line);border-radius:8px}
  .drow label,.drow .grow{min-width:100%}.drow button{width:100%}
  .wrap{padding-bottom:40px}
  .twocol,.checks,.metrics{grid-template-columns:1fr}
  .chain>li{grid-template-columns:1fr;gap:2px}
  .flow{grid-template-columns:1fr}
  .hero h1{font-size:26px}.focus li{grid-template-columns:minmax(0,1fr)}
  .claim summary{grid-template-columns:auto 1fr}.claim .ctext{grid-column:1/-1}.claim .kind{display:none}
  .top .in{gap:8px}.brand span{display:none}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{.top,.decision{display:none}}

/* Focused reference workspace */
.intent{margin-top:24px}.review-signals{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:20px 0}
.signal{border-top:3px solid var(--ok)}.signal.uncertainty{border-color:var(--warn)}
.signal p{font-size:14px}.signal .btn{margin-top:10px}
.risk-workspace{background:#fff;border:1px solid var(--line);border-radius:12px;padding:24px}
.risk-workspace>.overline{color:var(--bad)}
.impact-strip{display:flex;align-items:center;gap:12px;margin:20px 0 8px;font-size:13px}
.impact-strip span{flex:1;padding:12px;background:var(--src-bg);border-radius:6px}
.code-heading{display:flex;justify-content:space-between;gap:12px;margin:20px 0 8px;font-size:12px;color:var(--muted)}
.diff{background:#f8fafc;border:1px solid var(--line);border-radius:6px;max-height:360px;overflow:auto;padding:12px;font:12px/1.7 var(--mono);tab-size:4}
.diffline{display:block;min-width:max-content}.diffline.add{background:#dcf3e7;color:#145735}.diffline.remove{background:#ffe3df;color:#8d2721}
.risk-evidence{border-left:3px solid var(--warn);padding:12px;font-size:14px;background:var(--warn-bg)}
.code-detail{margin:16px 0}.code-detail summary,.audit>summary{cursor:pointer;font-weight:500;padding:8px 0}
.license-text{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.confidence-note{font-size:14px}.confidence-note p{color:var(--muted)}
#refused{margin:16px 0}.refusal h3{margin-top:8px}.refusal p{font-size:14px}
#refused .stack{display:grid;grid-template-columns:1fr 1fr;gap:16px}
select{display:block;width:100%;min-width:0;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--text);font:14px var(--sans)}
.snapshot-note{font-size:12px;color:var(--muted);margin-top:8px}
#overview{margin-top:24px}
.decision{position:static;margin:24px 0;padding:24px;border:1px solid var(--line);border-radius:12px;box-shadow:none}
.decision>p{font-size:14px}.audit{margin:32px 0;border-top:1px solid var(--line);padding-top:16px}
.audit .rail{position:static;max-height:none;grid-template-columns:1fr 1fr;overflow:visible}
@media(max-width:700px){.review-signals,#refused .stack,.audit .rail{grid-template-columns:1fr}.risk-workspace,.decision{padding:16px}.impact-strip{flex-direction:column;align-items:stretch}.impact-strip>b{transform:rotate(90deg);align-self:center}.code-heading{flex-direction:column}.diff{max-height:300px}.top .in{gap:6px}.brand{font-size:13px}#open-principles{display:none}nav a{font-size:12px;padding:8px}.wrap{padding-bottom:32px}.drow{flex-direction:column;align-items:stretch;gap:14px}.drow label,.drow .grow,.drow button,.drow .btn{width:100%;min-width:0}.drow fieldset.seg3{flex-direction:column;align-items:flex-start;gap:10px}.drow fieldset.seg3 label{width:auto;min-height:24px;padding:4px 0}.unknowns label{padding:8px 0}.card,.sec{scroll-margin-top:96px}}
/* Compact review path; long evidence remains available on demand. */
.snapshot-note{font-size:12px;color:var(--muted);margin-top:8px}
#overview{margin-top:24px}
.decision{position:static;margin:24px 0;padding:24px;border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}
.brief-item{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;margin:16px 0;min-width:0}
.provtag{display:inline-flex;align-items:center;gap:7px;justify-self:start;padding:4px 8px;border:1px solid var(--line);border-radius:6px;font-size:12px;line-height:1.5;max-width:100%;white-space:normal}
.provtag .ic{flex:0 0 14px}.briefrefs{display:flex;flex-wrap:wrap;gap:8px}
.risk-review{margin:24px 0}.risk-review>.sec{margin-top:20px}.risk-review h3{font-size:16px}
.risk-review .stack{gap:12px}.risk-context{margin:8px 0;font-size:13px}.risk-context summary{cursor:pointer;color:var(--muted)}
body:not([data-outcome=accept]) .risk-review .ans,body:not([data-outcome=accept]) .risk-review fieldset,body:not([data-outcome=accept]) .risk-review .risk-context:has([data-note-for]){display:none}
body:not([data-outcome=accept]) .unknowns input{display:none}
.seg3 label{min-height:40px}.reason-row{margin-top:20px}.audit{margin:24px 0;border-top:1px solid var(--line);padding-top:16px}
.diff{overflow-x:auto;max-width:100%;tab-size:4}.diffline,.source-line{display:block;min-width:max-content;line-height:1.65}.line-number{display:inline-block;width:4em;color:#64748b;user-select:none}
.k,.kt,.kd{color:#6941c6;font-weight:600}.s,.s1,.s2{color:#067647}.c,.c1,.cm{color:#667085;font-style:italic}.nf,.nc{color:#175cd3}.m,.mi{color:#b54708}
.diffline.add{border-left:3px solid #15803d}.diffline.remove{border-left:3px solid #b42318}
@media(max-width:600px){.technical-meta{display:none}.rhead{padding-top:8px}.decision{padding:16px}.provtag{font-size:11px}.brief-item{gap:8px}.drow{align-items:stretch}.drow .outcomes{display:grid;gap:8px}.risk-review .seg3{display:grid}}

"""

JS = r"""
(function(){
document.documentElement.classList.add('js');
var D=JSON.parse(document.getElementById('rr-data').textContent);
var DC=window.DecisionContract;
var $=function(s,r){return (r||document).querySelector(s)}, $$=function(s,r){return Array.prototype.slice.call((r||document).querySelectorAll(s))};
var draft={outcome:'',reason:'',refusals:{},findings:{},unknowns:{},notes:{}};
function show(){
  var h=(location.hash||'#receipt').slice(1),v=['queue','receipt','measurement'].indexOf(h)>=0?h:'receipt';
  if(h.indexOf('claim-')===0)v='receipt';
  ['queue','receipt','measurement'].forEach(function(n){$('#view-'+n).hidden=n!==v});
  $$('nav a').forEach(function(a){a.removeAttribute('aria-current');if(a.dataset.view===v)a.setAttribute('aria-current','page')});
  if(h.indexOf('claim-')===0){var el=document.getElementById(h);if(el){reveal(el)}}else window.scrollTo(0,0);
}
window.addEventListener('hashchange',show);
$$('[data-refusal] select').forEach(function(t){t.addEventListener('change',function(){draft.refusals[t.closest('[data-refusal]').dataset.refusal]=t.value;update()})});
$$('[data-note-for]').forEach(function(i){i.addEventListener('input',function(){var id=i.dataset.noteFor;if(i.value.trim())draft.notes[id]=i.value.trim();else delete draft.notes[id];update()})});
$$('[data-finding]').forEach(function(f){$$('input[type=radio]',f).forEach(function(r){r.addEventListener('change',function(){draft.findings[f.dataset.finding]=r.value;update()})})});
$$('[data-unknown] input').forEach(function(c){c.addEventListener('change',function(){var id=c.closest('[data-unknown]').dataset.unknown;if(c.checked)draft.unknowns[id]=true;else delete draft.unknowns[id];update()})});
$('[name=reason]').addEventListener('input',function(){draft.reason=this.value;update()});
$$('[name=outcome]').forEach(function(r){r.addEventListener('change',function(){draft.outcome=this.value;update()})});
function decisionInput(){
  var refusals=[],findings=[];
  D.contract.refusals.forEach(function(r){if(draft.refusals[r.id])refusals.push({refusalId:r.id,positionId:draft.refusals[r.id]})});
  D.contract.findings.forEach(function(id){if(draft.findings[id])findings.push({findingId:id,positionId:draft.findings[id]})});
  var acknowledged=D.contract.unknowns.filter(function(id){return !!draft.unknowns[id]});
  return draft.outcome==='accept'?{refusalPositions:refusals,findingPositions:findings,acknowledgedUnknowns:acknowledged}:{refusalPositions:[],findingPositions:[],acknowledgedUnknowns:[]};
}
function errors(){
  if(!draft.outcome)return [{code:'outcome_missing',message:'Choose accept, request changes, or escalate.'}];
  var input=decisionInput();
  return DC.validateDecision(draft.outcome,draft.reason,input.refusalPositions,input.findingPositions,input.acknowledgedUnknowns,D.contract);
}
/* Point each contract error at the field that can fix it, without clearing input. */
function fieldIdFor(err){
  if(err.code==='reason_missing'||err.code==='reason_placeholder')return 'reason';
  if(err.code==='outcome_missing'||err.code==='outcome_invalid')return 'outcome';
  var m=/^([A-Z]+\d+):/.exec(err.message||'');
  return m?m[1]:'outcome';
}
function errorTarget(id){
  if(id==='reason')return $('[name=reason]');
  if(id==='outcome')return $('.outcomes');
  return document.querySelector('[data-refusal="'+id+'"] select')||
         document.querySelector('[data-finding="'+id+'"] fieldset')||
         document.querySelector('[data-unknown="'+id+'"] input');
}
function clearFieldErrors(){
  $$('.field-error').forEach(function(p){p.hidden=true;p.textContent='';});
  $$('[aria-invalid=true]').forEach(function(el){el.removeAttribute('aria-invalid');});
  $$('.refusal.invalid,.finding.invalid,.seg3.invalid').forEach(function(el){el.classList.remove('invalid');});
}
function showFieldErrors(errs){
  clearFieldErrors();
  var groups={},order=[];
  errs.forEach(function(e){var id=fieldIdFor(e);if(!groups[id]){groups[id]=[];order.push(id);}groups[id].push(e.message);});
  order.forEach(function(id){
    var node=document.getElementById('err-'+id);
    if(node){node.textContent=groups[id].join(' ');node.hidden=false;}
    var target=errorTarget(id);
    if(!target)return;
    if(id==='outcome'||target.tagName==='FIELDSET'){target.classList.add('invalid');}
    else{target.setAttribute('aria-invalid','true');}
    if(/^(REF|OOR)/.test(id)){
      var card=document.querySelector('[data-refusal="'+id+'"], [data-finding="'+id+'"]');
      if(card)card.classList.add('invalid');
    }
  });
  return order;
}
function comment(){
  var input=decisionInput();
  function withNote(id,line){return draft.notes[id]?line+' -- '+draft.notes[id]:line}
  var lines=['/receipt '+(draft.outcome||'accept')+' '+(draft.reason.trim()||'[your reason]'),'Head: '+D.headSha];
  input.refusalPositions.forEach(function(p){lines.push(withNote(p.refusalId,p.refusalId+': '+p.positionId))});
  input.findingPositions.forEach(function(p){lines.push(withNote(p.findingId,p.findingId+': '+p.positionId))});
  input.acknowledgedUnknowns.forEach(function(id){lines.push(id+': acknowledged')});
  return lines.join('\n');
}
function update(){
  var acceptance=draft.outcome==='accept';
  document.body.dataset.outcome=draft.outcome||'none';
  $$('.risk-review select,.risk-review fieldset,.risk-review [data-note-for],.risk-review [data-unknown] input').forEach(function(el){el.disabled=!acceptance;});
  var chosen=D.contract.refusals.filter(function(r){return draft.refusals[r.id]}).length
           +D.contract.findings.filter(function(id){return draft.findings[id]}).length;
  var total=D.contract.refusals.length+D.contract.findings.length;
  var acked=D.contract.unknowns.filter(function(id){return draft.unknowns[id]}).length;
  $$('[data-refusal]').forEach(function(x){x.classList.toggle('done',!!draft.refusals[x.dataset.refusal])});
  $$('[data-finding]').forEach(function(x){x.classList.toggle('done',!!draft.findings[x.dataset.finding])});
  $$('[data-unknown]').forEach(function(x){x.classList.toggle('done',!!draft.unknowns[x.dataset.unknown])});
  $('#m-answers').textContent=chosen+' of '+total+' chosen';
  $('#m-unknowns').textContent=acked+' of '+D.contract.unknowns.length;
  var prompts={accept:'Your reason for accepting the listed risks',changes:'What must change, in your own words',escalate:'Why this needs a code or domain owner'};
  var readyText={accept:'Draft ready. Posting it would record acceptance of the listed risks. Nothing is recorded here.',
                 changes:'Draft ready. Posting it requests changes. Nothing is recorded here.',
                 escalate:'Draft ready. Posting it routes the gap to a code or domain owner; the decision stays pending owner judgement.'};
  $('[name=reason]').setAttribute('placeholder',prompts[draft.outcome]||'Your reason in your own words');
  $('#comment-preview').textContent=comment();
  var errs=errors(), ready=!!draft.outcome&&errs.length===0;
  var stale=!!document.querySelector('[data-stale=true]');
  if(stale){ready=false;errs=[{code:'receipt_stale',message:'Evidence outdated. Wait for a refreshed receipt before posting a decision.'}];}
  $('#copy-comment').disabled=!ready;
  if(!draft.outcome){clearFieldErrors();$('#first-error').hidden=true;$('#dstate').textContent='No decision selected.'}
  else if(ready){clearFieldErrors();$('#first-error').hidden=true;$('#dstate').textContent=readyText[draft.outcome]}
  else{
    var fields=showFieldErrors(errs);
    $('#first-error').hidden=false;
    $('#dstate').textContent=errs[0].message+(fields.length>1?' '+fields.length+' fields need attention.':'');
  }
  $('#dstate').classList.toggle('ready',ready);
}
$('#first-error').addEventListener('click',function(){
  var errs=errors();if(!errs.length)return;
  var target=errorTarget(fieldIdFor(errs[0]));if(!target)return;
  var focus=target.tagName==='FIELDSET'?target.querySelector('input'):target;
  if(target.scrollIntoView)target.scrollIntoView({block:'center'});
  if(focus)focus.focus({preventScroll:true});
});
$('#decision').addEventListener('submit',async function(ev){
  ev.preventDefault();
  if($('#copy-comment').disabled)return;
  try{await navigator.clipboard.writeText(comment());$('#dstate').textContent='Copied. Review and post it in the PR. No decision has been recorded.'}
  catch(err){$('#comment-preview').closest('details').open=true;$('#dstate').textContent='Select and copy the comment shown below, then post it in the PR.'}
});

/* Expand evidence in place, including its collapsed parent. */
function reveal(el){for(var p=el.parentElement;p;p=p.parentElement){if(p.tagName==='DETAILS')p.open=true}if(el.tagName==='DETAILS')el.open=true;el.scrollIntoView({block:'start'})}
$$('[data-evidence]').forEach(function(b){b.addEventListener('click',function(){reveal(document.getElementById(b.dataset.evidence))})});
/* dialogs, details links */
$$('[data-open-dialog]').forEach(function(b){b.addEventListener('click',function(){document.getElementById(b.dataset.openDialog).showModal()})});
$$('[data-close-dialog]').forEach(function(b){b.addEventListener('click',function(){b.closest('dialog').close()})});
$$('[data-open]').forEach(function(a){a.addEventListener('click',function(ev){ev.preventDefault();var el=document.getElementById(a.dataset.open);reveal(el)})});
$('#open-principles').addEventListener('click',function(){$('#principles').showModal()});
show();update();
})();
"""


def build(receipt, model, triage):
    contract = decision.contract_from_receipt(receipt)
    data = {
        "receiptId": receipt["receiptId"],
        "requirement": local_requirement_id(receipt["requirement"]["id"]),
        "baseSha": receipt["subject"]["baseSha"],
        "headSha": receipt["subject"]["headSha"],
        "contract": contract,
        "unknowns": contract["unknowns"],
    }
    nav = (f'<a href="#receipt" data-view="receipt">Review R2283</a>'
           f'<a href="#queue" data-view="queue">Concept &amp; samples</a>'
           f'<a href="#measurement" data-view="measurement">Evidence &amp; lessons</a>')
    body = (render_queue(triage, receipt) + render_receipt(receipt) + render_measurement(model, triage, receipt)
            + render_dialog())
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review Receipt · HackJunction 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{CSS}</style>
</head>
<body>
<div class="top"><div class="in">
  <div class="brand"><i></i><span>Review Receipt</span></div>
  <nav aria-label="Views">{nav}</nav>
  <button type="button" class="btn" id="open-principles">Principles and limits</button>
</div></div>
<main class="wrap">
{body}
<p class="foot">Generated by engine/render.py from {e(RECEIPT.name)}, {e(MODEL_RUN.name)} and {e(TRIAGE.name)}. Statuses and routing are copied from the engine’s output, not computed here.</p>
</main>
<script id="rr-data" type="application/json">{json.dumps(data).replace("<", "\\u003c")}</script>
<script>{DECISION_JS}</script>
<script>{JS}</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    receipt = json.loads(RECEIPT.read_text())
    model = json.loads(MODEL_RUN.read_text())
    triage = json.loads(TRIAGE.read_text())
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(line.rstrip() for line in build(receipt, model, triage).splitlines()) + "\n")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
