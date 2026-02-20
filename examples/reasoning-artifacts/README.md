# Reasoning Pipeline Artifacts

<!-- See: ../../docs/cddl-extraction-methodology.md for the full extraction process -->
<!-- See: ../../agent-conversation.cddl for the schema produced by this pipeline -->
<!-- See: ../DATASET_MANIFEST.md for the empirical dataset analyzed -->

This directory contains the intermediate reasoning artifacts produced by the 4-stage extraction pipeline that derived the CDDL schema from 221 empirical agent session traces.

## Pipeline Overview

```
221 CVE-Bench Traces (4 agent formats)
          ↓
    [Stage 1: RLM]
          ↓
  01-rlm-extraction-cddl-unification.md ← Pattern extraction across formats
          ↓
    [Stage 2: Agent0]
          ↓
  02-agent0-questions-cddl-merge.md ← 12 probing questions challenging assumptions
          ↓
    [Stage 3: Quint]
          ↓
  03-quint-decision-DRR-cddl-unification.md ← Evidence-backed decision (0.80 confidence)
          ↓
    [Stage 4: Council]
          ↓
  04-council-deliberation-cddl-unification.md ← Multi-perspective consensus (0.71 score)
          ↓
    [Output: CDDL Schema]
          ↓
  agent-conversation.cddl (553 lines, 53% comment density)
```

## Artifacts

### Stage 1: RLM Extraction

**File**: `01-rlm-extraction-cddl-unification.md` (43KB, ~900 lines)

**Tool**: `xor.research.rlm.extraction`

**Input**: Sample traces from 4 agent implementations (3-5 per agent)

**Output**: Structured extraction of common patterns and format-specific quirks

**Key Findings**:
- Timestamps: 4/4 formats use timestamps (2 RFC 3339, 2 epoch ms)
- Session IDs: 4/4 have session identifiers (UUID v4, v7, SHA-256)
- Tool calls: 4/4 have tool invocation records with varied naming
- Reasoning: 2/4 formats include explicit reasoning/thinking entries
- Vendor metadata: All 4 require `vendor-extension` mechanism

**Notable Patterns**:
- Field promotion principle: 4/4 agents → REQUIRED in CDDL
- Format tolerance: 2+ agents with different formats → support BOTH
- Semantic equivalence mapping: `tool_use` → `tool-call-entry`

### Stage 2: Agent0 Question Generation

**File**: `02-agent0-questions-cddl-merge.md` (23KB, ~480 lines)

**Tool**: `xor.research.agent0.generate_curriculum_tasks`

**Input**: RLM extraction results

**Output**: 12 probing questions challenging assumptions

**Question Categories**:
- **CHALLENGE** (5 questions): "How do you handle timestamp format variance?" → led to `abstract-timestamp = tstr / number`
- **ASSUME** (3 questions): "Can file attribution be fully derived?" → led to separation of session vs file-attribution
- **CONTRADICT** (4 questions): "What if vendor extensions conflict?" → led to `extension-key = tstr / int` dual compatibility

**Example Questions**:
- Q1: Should `verifiable-agent-record` require `session` OR `file-attribution` OR both?
- Q3: Can file attribution be FULLY derived from session trace entries?
- Q6: How should vendor extensions handle JSON (string keys) vs CBOR (int keys)?
- Q10: Henk's `tool` field collides with our `tool-call-entry` - how to resolve?

### Stage 3: Quint Evidence-Based Decision

**File**: `03-quint-decision-DRR-cddl-unification.md` (45KB, ~950 lines)

**Tool**: `xor.research.quint.standalone.analyze_documents`

**Input**: Agent0 questions + RLM extractions + 221 trace files

**Output**: Decision Record with 0.80 confidence score

**Evidence Sources**:
- 221 CVE-fixing session traces (primary evidence)
- 4 agent implementation formats (cross-validation)
- Henk's original file attribution schema (expert input)
- IETF RFC 8610 (CDDL spec), RFC 9052 (COSE), RFC 3339 (timestamps)

**Key Decisions**:
| Question | Decision | Confidence | Evidence Count |
|:---------|:---------|:-----------|:---------------:|
| Q1: Root type structure | session-trace PRIMARY, file-attribution COMPLEMENTARY | 0.85 | 221/221 traces have session, 45/221 have file metadata |
| Q3: Derivability | Partially derivable; `content_hash` requires external data | 0.78 | Tool calls reference files (100%), but hashes absent (95%) |
| Q6: Extension keys | `extension-key = tstr / int` for JSON/CBOR dual support | 0.82 | JSON uses strings (4/4), CBOR benefits from int keys |
| Q10: Naming collision | Rename `tool` to `recording-agent`, merge into `agent-meta` | 0.76 | Avoids ambiguity with `tool-call-entry` |

### Stage 4: Council Multi-Perspective Deliberation

**File**: `04-council-deliberation-cddl-unification.md` (12KB, ~250 lines)

**Tool**: `xor.research.strategy.council`

**Input**: Quint DRR + strategic considerations

**Output**: Consensus score 0.71 with 9 mandatory corrections

**Perspectives**:
- **Mathematician**: Formal invariants (temporal ordering, tool call pairing)
- **Creative**: Vendor extension flexibility for future agent types
- **Skeptic**: Attack vectors (signature stripping, timestamp manipulation)

**Corrections Applied**:
- #7: Add `contributor` field to `tool-call-entry` for multi-agent attribution
- #9: Remove XOR-internal references from CDDL header

## Reasoning Tools

These artifacts were generated using XOR's proprietary reasoning pipeline (not included in this repository):

### 1. RLM (Reasoning Learning Module)
- **Purpose**: Extract patterns from unstructured data (session traces, documents)
- **Method**: LLM-based pattern recognition with structured output schemas
- **Module**: `xor.research.rlm.extraction`

### 2. Agent0 (Curriculum Generation)
- **Purpose**: Generate probing questions that challenge assumptions and surface edge cases
- **Method**: Meta-learning curriculum generation inspired by adversarial testing
- **Module**: `xor.research.agent0.generate_curriculum_tasks`

### 3. Quint (Evidence-Backed Reasoning)
- **Purpose**: Make decisions with explicit evidence citations and confidence scores
- **Method**: Retrieval-augmented generation with confidence calibration
- **Module**: `xor.research.quint.standalone.analyze_documents`

### 4. Council (Multi-Perspective Deliberation)
- **Purpose**: Validate decisions from multiple viewpoints (mathematician, creative, skeptic)
- **Method**: Multi-agent deliberation with consensus scoring
- **Module**: `xor.research.strategy.council`

## Reproducibility

To reproduce this reasoning pipeline on new data:

```bash
# XOR monorepo (tools not included in this repository)
cd /path/to/xor

# Stage 1: RLM Extraction
python -m xor.research.rlm.extraction \
  --input bench/runs/arvo-250iq/run-2026-02-07/*.{json,jsonl} \
  --output .quint/rlm-extractions/cddl-unification.md

# Stage 2: Agent0 Questions
python -m xor.research.agent0 generate_curriculum_tasks \
  --input .quint/rlm-extractions/cddl-unification.md \
  --output .quint/agent0-questions/cddl-merge.md \
  --num-questions 12

# Stage 3: Quint Decision
python -m xor.research.quint.standalone analyze_documents \
  --questions .quint/agent0-questions/cddl-merge.md \
  --evidence bench/runs/arvo-250iq/run-2026-02-07/ \
  --output .quint/decisions/DRR-cddl-unification.md

# Stage 4: Council Deliberation
python -m xor.research.strategy council \
  --input .quint/decisions/DRR-cddl-unification.md \
  --output .quint/council-deliberations/cddl-unification.md
```

## Transparency & Trust

These artifacts are included to demonstrate:

1. **Empirical Grounding**: The CDDL schema was not designed arbitrarily, but derived from analyzing 221 real agent session traces.

2. **Reasoning Chain**: Every design decision has a traceable lineage:
   - RLM extraction → identified patterns
   - Agent0 questions → surfaced edge cases
   - Quint decision → evidence-backed choices with confidence scores
   - Council deliberation → multi-perspective validation

3. **Explainability**: Reviewers can audit the reasoning process and challenge specific decisions by examining the evidence and confidence scores.

4. **Reproducibility**: The pipeline can be re-run on new agent formats or updated datasets to evolve the schema as the ecosystem changes.

## Cross-References

- **Extraction Methodology**: [docs/cddl-extraction-methodology.md](../../docs/cddl-extraction-methodology.md)
- **Agent Type Mapping**: [docs/agent-type-mapping-table.md](../../docs/agent-type-mapping-table.md)
- **CDDL Schema**: [agent-conversation.cddl](../../agent-conversation.cddl)
- **I-D Appendix B** (Empirical Basis): [draft-birkholz-verifiable-agent-conversations.md#appendix-b](../../draft-birkholz-verifiable-agent-conversations.md#appendix-b-empirical-basis)
- **Dataset Manifest**: [../DATASET_MANIFEST.md](../DATASET_MANIFEST.md)

## License

These artifacts are provided for transparency and reproducibility. The reasoning tools themselves are proprietary XOR software and not included in this repository.
