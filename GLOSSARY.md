# Review Receipt

Review Receipt is a human-decision system for AI-written code. Its language separates observed evidence, AI interpretation, unresolved risk, and human ownership.

## Language

**Evidence-led review**:
A human review based on the requirement, observed evidence, limitations, residual risks, and unresolved questions, without requiring the reviewer to read source code. Source and diffs are optional corroboration, and insufficient evidence can still prevent a decision.
_Avoid_: No-code review, automatic review

**Decision brief**:
A plain-language account of what the evidence supports, which material risks and unknowns remain, how the AI's claims are classified, and what the human must decide. It presents receipt evidence without requiring source-code reading or claiming a semantic correctness verdict.
_Avoid_: AI summary, trust verdict

**AI claim**:
A statement made by the AI reviewer about a change. Its evidence classification is independent of the AI's confidence and does not become human knowledge merely by appearing in a receipt.
_Avoid_: Fact, finding, verified truth

**Test-backed claim**:
An AI claim whose linked named tests ran with the outcomes expected by those evidence associations. The links do not by themselves prove that the tests establish the claim's full meaning.
_Avoid_: Proven claim, correct claim

**Contradicted claim**:
An AI claim for which a linked test outcome conflicts with the outcome its evidence association treats as expected. This mechanical conflict does not by itself contradict the claim's prose, identify an AI hallucination, or establish a defect.
_Avoid_: Hallucination, false claim

**Unsupported claim**:
An AI claim for which the cited executed evidence is absent or insufficient. It is unproven rather than proven false.
_Avoid_: Hallucination, failed claim

**Source-only claim**:
An AI claim whose cited source range resolves but which has no executed behavioural evidence establishing it. Neither the source's semantic support for the prose nor runtime behaviour is established.
_Avoid_: Verified behaviour, tested claim

**Refusal**:
A consequential requirement, product, or ownership question that the AI reviewer declines to decide. A human answers with an explicit position; refusal is not a model malfunction or an automatically identified defect.
_Avoid_: AI failure, risk position

**Outside-requirement item**:
A change or behaviour not covered by the stated requirement. It is a candidate scope concern rather than proof of a defect, and a human dispositions it as accepted scope, requiring change, or needing owner judgement.
_Avoid_: Real finding, scope creep

**Provenance**:
The origin of a receipt statement: harness-recorded observation, AI interpretation, deterministic engine classification, team-authored explanation, or human decision. These origins are distinct forms of authority.
_Avoid_: Trust level, evidence

**Residual risk**:
A named uncertainty, limitation, or consequence that remains after the available checks. Accepting a change requires the named human to acknowledge its recorded residual risks explicitly.
_Avoid_: Unknown, minor issue

**Decision contract**:
The requirements for a valid human decision: an outcome, the appropriate human reason, any required structured positions and residual-risk acknowledgements, and binding to the reviewed evidence and commit. Presentation feedback never substitutes for authoritative validation.
_Avoid_: Questionnaire, copied comment, browser sign-off

**Pinned snapshot**:
A presentation of a receipt bound to a particular base, head, and evidence fingerprint rather than live pull-request state. Its source evidence and decision must not be treated as current after those inputs change.
_Avoid_: Live review, current approval

**Request changes**:
A human decision outcome stating why the change should not be accepted as it stands. It may reference a specific concern but does not require the reviewer to complete acceptance acknowledgements or prove that every concern is a defect.
_Avoid_: Escalation, failed evidence

**Escalation**:
A human decision outcome that routes a pending review to a code or domain owner because the current reviewer cannot resolve the remaining expertise or evidence gap. It neither accepts the change nor determines that it is defective.
_Avoid_: Rejection, request changes, approval
