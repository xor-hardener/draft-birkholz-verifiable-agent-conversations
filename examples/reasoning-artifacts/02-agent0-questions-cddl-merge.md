# Agent0 Probing Questions: CDDL Schema Merge

**Generated**: 2026-02-09
**Framework**: Agent0 Strategic Questioning (CHALLENGE / ASSUME / CONTRADICT)
**Context**: Merging Henk Birkholz's file attribution CDDL (`agent-conversation.cddl`) with XOR's conversation records CDDL (`ietf-abstract-types.cddl`) into a single IETF Internet-Draft

---

## Schemas Under Merge

| Property | Schema A (Henk) | Schema B (XOR) |
|----------|-----------------|----------------|
| Root type | `agent-convo-record` | `session-trace` |
| Primary lens | File attribution (which code was written by whom) | Session replay (what happened during the conversation) |
| Granularity | Per-file, per-line-range | Per-entry (user, assistant, tool-call, reasoning) |
| VCS model | `type` + `revision` (commit only) | `type`, `branch`, `commit`, `repository` |
| Extension mechanism | `anymap = { * label => value }` (untagged) | `vendor-extension = { vendor, version, data }` (tagged) |
| Signing | Not specified | COSE_Sign1 envelope (Section 9) |
| Evidence base | Henk's IETF experience (RFC 9334 co-author) | 221 CVE-fixing sessions across 4 agent formats |

---

## Questions

### Q1: CHALLENGE - Root Type Conflict: Who Becomes the Envelope?

> **Both schemas define a top-level record type. `agent-convo-record` is file-centric (root -> files -> conversations -> ranges). `session-trace` is event-centric (root -> entries -> tool-calls/responses). If one nests inside the other, which direction preserves both schemas' semantics? Does `agent-convo-record` embed a `session-trace` in its `metadata`, or does `session-trace` derive `agent-convo-record` as a computed view of its entries? What information is LOST in each direction?**

**Challenge type**: `challenge`
**Why it matters**: This is the fundamental architectural decision. Nesting Henk's record inside XOR's session-trace demotes file attribution to a post-hoc appendix. Nesting XOR's session-trace inside Henk's record demotes the real-time conversation to metadata. Neither option is neutral -- the nesting direction declares which perspective is primary, and IETF reviewers will notice. A third option (peer relationship: two independent types in the same draft, linked by shared session-id) avoids hierarchy but doubles the spec surface area.
**Evidence to answer it**: Map the information flow: can `agent-convo-record.files[].conversations[].ranges[]` be mechanically derived from `session-trace.entries[]` where entry type is `tool-call` with name `Edit`/`Write`? If yes, file attribution is a computed view and need not be a separate root type. If not, identify what file attribution data cannot be reconstructed from conversation entries.

---

### Q2: ASSUME - Henk's Authority and the Primary Lens Problem

> **Henk Birkholz co-authored RFC 9334 (RATS Architecture) and positioned this draft under IETF Security Area with file attribution as the primary use case. Assuming Henk sees the standard as "code provenance for AI-generated code" (who wrote which lines), does XOR's session-replay model (what happened during the conversation) subordinate his work to a supporting role? How do you merge without the senior IETF author perceiving his contribution as demoted to a "derived view" of XOR's richer schema?**

**Challenge type**: `assume`
**Why it matters**: IETF drafts require author consensus. If Henk perceives the merge as XOR co-opting his draft to carry a different (session-replay) standard, he can block progression. The merge strategy must frame file attribution and session replay as complementary perspectives of the same underlying reality, not as primary/secondary. The draft-birkholz-verifiable-agent-conversations.md already names Henk as first author and Tobias (XOR) as second -- the merge must respect this authorship hierarchy.
**Evidence to answer it**: Read `draft-birkholz-verifiable-agent-conversations.md` introduction (lines 60-73). Henk's four goals are: (1) conversation recording fidelity, (2) extensible conversation structure, (3) RATS evidence generation, (4) SCITT auditability. Does XOR's schema serve ALL four goals, or only goals 1-2 while ignoring goals 3-4?

---

### Q3: CHALLENGE - Tool-Call to File Attribution Bridge

> **When a `tool-call-entry` with `name: "Edit"` includes `input: { file_path: "/src/main.py", old_string: "...", new_string: "..." }`, this implicitly defines a file modification with a line range. Henk's `range` type captures `{ start_line, end_line, content_hash, contributor }`. Can a validator mechanically derive Henk's `file.conversations[].ranges[]` FROM a sequence of tool-call/tool-result entries? What information is present in Henk's schema that CANNOT be reconstructed from conversation entries alone?**

**Challenge type**: `challenge`
**Why it matters**: If file attribution is fully derivable from conversation entries, then Schema A is a computed projection of Schema B and need not exist as a separate type -- it can be an "informative algorithm" in the I-D appendix. If file attribution contains non-derivable information (e.g., `content_hash` computed over the final file state, not the diff), then both types must coexist. The answer determines whether the merge produces one root type or two.
**Evidence to answer it**: Take 5 real CVE-fixing sessions from `bench/runs/arvo-250iq/`. For each, trace the tool-call entries that modify files. Attempt to reconstruct a complete `agent-convo-record` from only the conversation entries. Document every field that cannot be reconstructed (likely: `content_hash`, `contributor.type` when the agent delegates to sub-agents, `vcs.revision` at recording time vs. conversation time).

---

### Q4: CONTRADICT - Selfish Ledger vs. Vendor-Neutral Standard

> **XOR's GTM Playbook positions the IETF standard to "compound XOR's data moat" (221 traces = largest evidence corpus) and make CVE-Bench the reference implementation. But IETF RFC 2026 Section 4.1 requires that standards "not favor one vendor." Where does XOR's "first-mover advantage in trace format definition" cross the line from legitimate standard-setting to vendor lock-in that IETF reviewers from Google, Microsoft, or OpenAI will reject?**

**Challenge type**: `contradict`
**Why it matters**: The tension is structural. XOR benefits from the standard because its 221 traces become the reference corpus. But if IETF reviewers perceive the abstract types as "XOR's internal format with an IETF label," the draft will stall in review. The SAM-SWIRSKY-STRATEGIC-BRIEF explicitly says to position XOR as "the authority that AI companies benchmark against" -- this is the OPPOSITE of the vendor-neutral posture IETF demands. The merge must resolve this contradiction before submission.
**Evidence to answer it**: Audit `ietf-abstract-types.cddl` for XOR-specific or CVE-Bench-specific assumptions. Count how many design decisions cite XOR's evidence corpus vs. external evidence. Check whether the `trace-format-id` registry (Section 9, lines 368-373) privileges formats XOR has already implemented over formats it has not.

---

### Q5: CHALLENGE - Contributor Redundancy Across Schemas

> **Schema A has `contributor.model_id` at two levels: per-conversation and per-range (for agent handoffs). Schema B has `agent-meta.model-id` at session level and `assistant-entry.model-id` per response. In a multi-agent session where Claude Code spawns subagents (Task tool with Explore/Bash agents), which `model_id` is authoritative for a given line range? Does the merged schema need a per-range contributor that can differ from the session-level agent?**

**Challenge type**: `challenge`
**Why it matters**: Multi-agent sessions are increasingly common (Claude Code spawns subagents, Codex delegates to sub-models). Henk's schema handles this elegantly: each `range` can override the `conversation`-level `contributor`. XOR's schema does NOT have per-entry model attribution -- `model-id` in `assistant-entry` applies to the response, not to the code changes within it. If a subagent (running a different model) makes a tool-call that edits code, Henk's schema can attribute it correctly; XOR's cannot without extending `tool-call-entry` with a `contributor` field. The merge must either adopt Henk's per-range attribution or acknowledge that multi-agent provenance is out of scope.
**Evidence to answer it**: Find multi-agent sessions in the 221 CVE traces where Claude Code spawns a Task subagent. Check whether the subagent's model-id is recorded in tool-call entries. If not, this is an attribution gap that Henk's schema solves and XOR's does not.

---

### Q6: CONTRADICT - The `anymap` vs. `vendor-extension` Escape Hatch

> **Henk's schema uses `metadata: anymap` where `anymap = { * label => value }` with `label = any`. This accepts ANY key type (including integers, byte strings, booleans) as map keys. XOR's `vendor-extension` restricts keys to `tstr` (strings) and requires `vendor` and `version` provenance tags. These are contradictory extension philosophies. Does the merged schema adopt Henk's permissive approach (maximally extensible, minimally verifiable) or XOR's tagged approach (less extensible, auditable)? Can you justify either choice to BOTH Henk (who designed the permissive approach intentionally for CBOR compatibility) AND XOR's council (which explicitly rejected bare `any` in Correction 4)?**

**Challenge type**: `contradict`
**Why it matters**: This is not a cosmetic difference. `label = any` means CBOR integer keys are valid, which is essential for compact CBOR encoding (IETF norm). `* tstr => any` means only string keys are valid, which is JSON-compatible but CBOR-hostile. Henk's draft references CBOR (RFC 8949) as a primary representation; XOR's schema is "JSON-first" (line 34). The merge must reconcile JSON-first with CBOR-primary, and the extension mechanism is where this tension surfaces first.
**Evidence to answer it**: Check whether Henk's `anymap` with `label = any` was a deliberate CBOR optimization (allowing integer keys for compact encoding per RFC 8949 Section 3.1) or a placeholder ("placeholder for later" per line 15). If deliberate, XOR's `vendor-extension` must accommodate CBOR integer keys. If placeholder, XOR's tagged approach is the stronger design.

---

### Q7: ASSUME - VCS Scope Mismatch: Commits vs. Branches

> **Schema A's `vcs` has `type` + `revision` (a commit SHA). Schema B's `vcs-context` has `type`, `branch`, `commit`, `repository`. Schema A does not model branches. Is this an intentional design choice by Henk (provenance cares about specific commits, not the branch they were on) or an omission? When Henk's `agent-convo-record` is created from a feature branch that is later squash-merged, the `revision` points to a commit that no longer exists in the main branch history. Does the merged schema need branch context to make VCS references stable?**

**Challenge type**: `assume`
**Why it matters**: Git commits on feature branches can become unreachable after squash merge, rebase, or force push. A provenance record that only stores `revision: "abc123"` becomes unverifiable if that commit is garbage-collected. Schema B's addition of `branch` and `repository` provides context that survives branch operations. But Henk may have intentionally kept VCS minimal (commit SHAs are content-addressed, branches are mutable labels). The merge must decide whether VCS context is minimal (Henk) or rich (XOR), and document WHY.
**Evidence to answer it**: Check SCITT architecture (RFC draft referenced in Henk's I-D) for how it handles VCS references. Does SCITT assume immutable content addresses (aligning with Henk's commit-only model) or does it require mutable context (aligning with XOR's branch model)?

---

### Q8: CHALLENGE - Post-Hoc Attribution vs. Real-Time Recording

> **Schema A records post-hoc file attribution: after a conversation completes, which files were modified and by whom. Schema B records real-time conversation: as entries occur, each is timestamped and sequenced. Can one merged schema serve BOTH temporal perspectives? A post-hoc record may aggregate multiple conversations into a single file attribution (correct for provenance). A real-time record preserves the sequence of individual edits (correct for replay/audit). Do these perspectives conflict when a file is modified, reverted, and modified again in the same session?**

**Challenge type**: `challenge`
**Why it matters**: Consider a session where line 42 of `main.py` is edited by tool-call A (timestamp T1), reverted by tool-call B (T2), and re-edited by tool-call C (T3). Schema B preserves all three edits in sequence. Schema A's file attribution must decide: does line 42's `range` attribute to tool-call A (first author), tool-call C (final author), or all three (complete history)? The merge must specify whether file attribution is "current state" or "full history" -- they have different CDDL structures.
**Evidence to answer it**: Find CVE-fixing sessions where a file is modified multiple times. Check whether Henk's `conversations` array preserves ordering (it does -- array, not set). Determine if `ranges` within a `conversation` can overlap (Schema A does not prohibit this). Define the semantic: does a later `range` supersede an earlier one for the same lines?

---

### Q9: ASSUME - Signing Asymmetry: Henk Has None, XOR Has COSE_Sign1

> **XOR's schema includes a COSE_Sign1 signing envelope (Section 9) that wraps any serialized trace. Henk's schema has no signing mechanism. Henk's I-D introduction explicitly states goals 3 (RATS evidence generation) and 4 (SCITT auditability), both of which REQUIRE cryptographic signing. Does the merged draft adopt XOR's COSE_Sign1 envelope as the signing mechanism for Henk's file attribution records? If so, who defines the signing key management -- the I-D itself, or a separate key distribution draft?**

**Challenge type**: `assume`
**Why it matters**: Henk's goals 3 and 4 cannot be achieved without a signing mechanism, yet his CDDL does not define one. XOR's COSE_Sign1 envelope is the only signing mechanism on the table. Adopting it means Henk's draft inherits a dependency on RFC 9052 (COSE) and requires implementers to support CBOR for the signing envelope even if the trace payload is JSON. This is architecturally clean (Henk already references CBOR) but increases implementation complexity. The merge must decide whether signing is normative (MUST) or informative (MAY).
**Evidence to answer it**: Read Henk's I-D references: RFC 9052 (COSE), RFC 9334 (RATS), and draft-ietf-scitt-architecture. Determine whether RATS evidence generation requires COSE_Sign1 specifically or allows other signing mechanisms (JWS/RFC 7515 is also referenced). Check if XOR's COSE_Sign1 envelope can wrap Henk's `agent-convo-record` without modification.

---

### Q10: CONTRADICT - `tool` Type Collision

> **Schema A defines `tool = { name, version }` to identify the tool that GENERATED the conversation record (e.g., "claude-code v1.2.0"). Schema B defines `tool-call-entry` and `tool-result-entry` to model tool INVOCATIONS within the conversation (e.g., agent calls Edit, Bash, Read). These are semantically different uses of "tool": one is the recording agent, the other is the agent's actions. Does the merged schema use "tool" for the generator (Henk's meaning) or for invocations (XOR's meaning)? Using the same word for both creates ambiguity that IETF reviewers will flag.**

**Challenge type**: `contradict`
**Why it matters**: IETF drafts require precise terminology (BCP 14). "Tool" meaning two different things in the same spec is a guaranteed review comment. The merge must either rename one usage (e.g., Henk's `tool` -> `generator` or `recording-agent`) or namespace them (e.g., `recording-tool` vs. `invoked-tool`). The renaming choice signals whose terminology takes precedence.
**Evidence to answer it**: Search both schemas for all uses of "tool". In Schema A: `tool` appears once as a top-level optional field. In Schema B: `tool-call-entry` and `tool-result-entry` are entry types. Propose a consistent terminology that disambiguates without breaking either schema's existing references.

---

### Q11: CHALLENGE - The `conversation.url` to Entry Linkage Gap

> **Schema A's `conversation` type has `url: text` pointing to "the conversation that produced this code." Schema B has no concept of external conversation URLs -- entries are self-contained within the session-trace. When the merge occurs, does `conversation.url` point to a specific entry within a `session-trace` (requiring an entry-level addressability scheme like `session-id#entry-id`) or to an external system (e.g., a Claude Code sharing URL)? If the latter, the merged schema has two parallel reference systems: internal (entry-id linkage) and external (URL linkage), which creates a consistency verification burden.**

**Challenge type**: `challenge`
**Why it matters**: Henk's `conversation.url` enables external cross-referencing (a file's provenance record points to the conversation that produced it). XOR's entry-id linkage enables internal cross-referencing (tool-result points back to tool-call via call-id). The merge must define how these two reference systems interact. Can a `conversation.url` be a fragment reference into a `session-trace`? If so, the spec must define the URL scheme. If not, there are two disconnected reference graphs in one standard.
**Evidence to answer it**: Check whether any of the 4 agent formats provide shareable conversation URLs. Claude Code has sharing URLs (`https://claude.ai/share/...`). Do Gemini CLI, Codex CLI, or OpenCode? If only Claude does, `conversation.url` is effectively single-vendor, which conflicts with the 2+ implementation requirement.

---

### Q12: CONTRADICT - XOR's "Largest Evidence Corpus" vs. Henk's IETF Credibility

> **XOR positions its 221 CVE-fixing traces as the empirical foundation for the standard ("largest evidence corpus"). But Henk brings IETF process credibility (RFC co-authorship, RATS working group participation). The merge compounds both assets -- but whose contribution is more valuable for IETF adoption? If the standard passes IETF review on Henk's credibility but the reference implementation uses XOR's corpus, does XOR get the compounding advantage it seeks, or does Henk's authorship overshadow XOR's data contribution?**

**Challenge type**: `contradict`
**Why it matters**: XOR's strategic docs frame the IETF standard as a mechanism to "compound the data moat." But IETF standards are cited by RFC number and author names, not by dataset size. If the standard is known as "Birkholz's agent conversation standard" (as IETF citations will read), XOR's brand benefit is diluted. Conversely, without XOR's 221-trace evidence base, Henk's draft has no "running code" to demonstrate interoperability. The merge must structure authorship and acknowledgments to ensure both contributions are visible.
**Evidence to answer it**: Review IETF RFC authorship conventions. Do acknowledgment sections ("This work was informed by analysis of N traces from XOR's CVE-Bench") provide sufficient attribution for strategic visibility? Check how RFC 9334's acknowledgments section credits non-author contributors.

---

## Priority Ordering

### Must answer BEFORE merge can proceed (blocking)
1. **Q1** (Root type conflict) -- Determines the entire merged schema structure
2. **Q6** (anymap vs. vendor-extension) -- Determines the extension philosophy (JSON-first vs. CBOR-primary)
3. **Q10** (tool type collision) -- Must resolve terminology before drafting
4. **Q3** (tool-call to file bridge) -- Determines if file attribution is derivable or independent

### Must answer BEFORE Internet-Draft submission (critical)
5. **Q4** (selfish ledger vs. vendor-neutral) -- IETF review will surface this tension
6. **Q2** (Henk's authority) -- Author consensus is prerequisite for submission
7. **Q9** (signing asymmetry) -- Goals 3-4 require a signing mechanism
8. **Q8** (temporal perspectives) -- Semantic definition affects all implementers

### Should answer BEFORE reference implementation (important)
9. **Q5** (contributor redundancy) -- Multi-agent sessions need clear attribution
10. **Q7** (VCS scope) -- Stability of VCS references after merge/rebase
11. **Q11** (conversation.url linkage) -- Cross-reference system must be specified
12. **Q12** (XOR brand vs. Henk authorship) -- Strategic positioning for acknowledgments

---

## Strategic Risk Assessment

### Does the merge strengthen or weaken XOR's position?

**Strengthens IF:**
- The merged schema uses XOR's `session-trace` as the primary container (event-centric view becomes the standard)
- XOR's `vendor-extension` mechanism (tagged, auditable) replaces Henk's `anymap` (untagged, permissive)
- XOR's COSE_Sign1 envelope becomes the normative signing mechanism (aligns with Henk's goals 3-4)
- The 221-trace evidence corpus is cited as the empirical foundation in the I-D's abstract or introduction
- CVE-Bench becomes the conformance test suite (reference implementation advantage)

**Weakens IF:**
- Henk's file attribution becomes the primary container and XOR's conversation entries become "optional metadata"
- The `anymap` permissive extension approach wins (XOR loses the auditability advantage)
- IETF reviewers perceive the standard as XOR-biased and delay or reject it
- The merge requires XOR to delete or significantly restructure `ietf-abstract-types.cddl`, losing months of analysis work
- Henk's authorship and IETF reputation overshadow XOR's data contribution in citations

**Net Assessment**: The merge is POSITIVE-SUM if structured as peer schemas (session-trace for replay, agent-convo-record for attribution, both wrapped in COSE_Sign1 for verifiability). It is ZERO-SUM if one schema subsumes the other. The optimal merge strategy is:

1. **Henk's `agent-convo-record`** becomes a DERIVED TYPE -- a computed view that can be mechanically generated from a `session-trace` by walking tool-call entries that modify files
2. **XOR's `session-trace`** is the PRIMARY recording format (captures everything)
3. **COSE_Sign1** wraps either format independently (Henk's goal 3-4 satisfied, XOR's signing envelope adopted)
4. Both schemas coexist in the I-D, with a normative algorithm for deriving one from the other
5. The I-D abstract credits "empirical analysis of N agent implementations" (XOR's corpus) as the evidence base

This gives Henk his file attribution standard, gives XOR its session-replay standard, and the derivation algorithm proves they are formally related -- making the merged draft stronger than either standalone.

---

**Generated by**: Agent0 Strategic Questioning Framework
**Evidence corpus**: 2 CDDL schemas (57 + 478 lines), 1 Internet-Draft, 3 strategy documents, 1 prior Agent0 question set (15 questions)
**Next step**: Answer Q1, Q6, Q10, Q3 (blocking questions) before attempting the merge. Use Quint evidence analysis to produce a DRR for each answer.
