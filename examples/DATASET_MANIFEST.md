# CVE-Bench "arvo-250iq" Dataset Manifest

<!-- See: ../draft-birkholz-verifiable-agent-conversations.md#appendix-b-empirical-basis -->
<!-- See: ../agent-conversation.cddl for the schema derived from this dataset -->
<!-- See: ../docs/cddl-extraction-methodology.md for the extraction process -->

## Dataset Overview

- **Source**: CVE-Bench "arvo-250iq" benchmark
- **Total Sessions**: 221 CVE-fixing agent traces
- **CVEs**: 23 distinct vulnerabilities across 3 projects
- **Agents**: 4 implementations × multiple models
- **Task Domain**: Security vulnerability remediation (code fixing)
- **Collection Period**: February 7, 2026
- **Format Diversity**: 4 vendor-specific trace formats

## Agent Implementations

| Agent | Format | Extension | Sessions | Model(s) |
|:------|:-------|:----------|:---------|:---------|
| **Claude Code** | JSONL (one object per line) | `.jsonl` | ~55 | claude-opus-4-5, claude-sonnet-4-5 |
| **Gemini CLI** | Single JSON array | `.json` | ~55 | gemini-3-pro-preview, gemini-3-flash |
| **Codex CLI** | JSONL with envelope | `.jsonl` | ~55 | gpt-5.2 |
| **OpenCode** | Single JSON with metadata | `.json` | ~56 | claude-opus-4-5, gpt-5.2 |

## Project Coverage

| Project | CVEs | Description |
|:--------|:-----|:------------|
| **harfbuzz/harfbuzz** | 10 | Font rendering engine vulnerabilities |
| **openthread/openthread** | 7 | Thread protocol implementation issues |
| **darktable-org/rawspeed** | 6 | Raw image processing bugs |

## CVE Distribution

### harfbuzz/harfbuzz
- XOR-harfbuzz-ID-11033, ID-11060, ID-11081, ID-11522, ID-12292, ID-12424, ID-12442, ID-13114, ID-14055, ID-14074

### openthread/openthread
- XOR-openthread-ID-11376, ID-11628, ID-11646, ID-11722, ID-11737, ID-12057, ID-12078

### darktable-org/rawspeed
- XOR-rawspeed-ID-11078, ID-11429, ID-11456, ID-11458, ID-11616, ID-11717

## File Naming Convention

```
{agent}-{model}-{project}-{cve_id}-{attempt}-{artifact}.{ext}
```

**Examples**:
- `claude-claude-opus-4-5-harfbuzz-XOR-harfbuzz-ID-11033-0-session.jsonl` — Claude Code session trace
- `gemini-gemini-3-pro-preview-harfbuzz-XOR-harfbuzz-ID-12292-0.json` — Gemini CLI session trace
- `codex-gpt-5.2-openthread-XOR-openthread-ID-11376-0.json` — Codex CLI session trace
- `opencode-gpt-5.2-openthread-XOR-openthread-ID-11376-0.json` — OpenCode session trace

**Artifacts per session**:
- `*-session.jsonl` or `*.json`: Full agent conversation trace
- `*-fix.patch`: Generated patch file (if successful)
- `*-payload.json`: Benchmark metadata (CVE description, test commands, etc.)
- `*.json` (consolidated): Combined artifact for some agents

## Sample Traces

Minimal representative samples showing key message types from each agent:

- `examples/traces/claude-sample.jsonl` — Claude Code format (13 events, 99KB)
- `examples/traces/gemini-sample.json` — Gemini CLI format (single array)
- `examples/traces/codex-sample.json` — Codex CLI format (JSONL with envelope)
- `examples/traces/opencode-sample.json` — OpenCode format (metadata wrapper)

Full dataset available at: `bench/runs/arvo-250iq/run-2026-02-07/` (XOR monorepo)

## Trace Statistics

### Message Counts (Median per Agent)

| Agent | User Messages | Assistant Messages | Tool Calls | Tool Results |
|:------|:--------------|:-------------------|:-----------|:-------------|
| Claude Code | 5 | 8 | 12 | 12 |
| Gemini CLI | 4 | 7 | 10 | 10 |
| Codex CLI | 6 | 9 | 14 | 14 |
| OpenCode | 7 | 11 | 16 | 16 |

### Session Durations (Median)

- Claude Code: ~45 seconds
- Gemini CLI: ~38 seconds
- Codex CLI: ~52 seconds
- OpenCode: ~61 seconds

## Success Metrics

| Metric | Claude | Gemini | Codex | OpenCode |
|:-------|:-------|:-------|:------|:---------|
| **CVEs Attempted** | 23 | 23 | 23 | 23 |
| **Successful Fixes** | 18 | 16 | 19 | 17 |
| **Success Rate** | 78% | 70% | 83% | 74% |

## Empirical Findings

### Common Patterns (All 4 Agents)

1. **Timestamps**: 100% (4/4) include timestamps
   - 3 agents use RFC 3339 strings (`"2026-02-07T11:22:22.551Z"`)
   - 1 agent uses epoch milliseconds (`1707307336344`)
   - **Abstraction**: `abstract-timestamp = tstr / number`

2. **Session IDs**: 100% (4/4) include session identifiers
   - 2 agents use UUID v4
   - 1 agent uses UUID v7
   - 1 agent uses SHA-256 hash
   - **Abstraction**: `session-id = tstr`

3. **Tool Invocation**: 100% (4/4) record tool calls and results
   - Field names vary: `tool_use`, `function_call`, `apply_patch`
   - **Abstraction**: `tool-call-entry` + `tool-result-entry`

4. **Reasoning**: 50% (2/4) include explicit reasoning entries
   - Claude Code: `content[].type: "thinking"`
   - Codex CLI: `content[].type: "reasoning"`
   - Gemini/OpenCode: implicit (reasoning embedded in text)
   - **Abstraction**: Optional `reasoning-entry`

### Variance Requiring Abstraction

| Feature | Variance | CDDL Solution |
|:--------|:---------|:--------------|
| Timestamp format | String vs number | `tstr / number` |
| Session ID format | UUID v4/v7, SHA-256 | `tstr` (any string) |
| Extension keys | JSON strings, CBOR ints | `tstr / int` |
| Tool call naming | 4 different field names | Semantic mapping to `tool-call-entry` |

## Dataset Limitations

<!-- See: ../draft-birkholz-verifiable-agent-conversations.md#appendix-b-empirical-basis -->

1. **Domain Specificity**: All tasks are CVE vulnerability fixes (security code remediation). Generalizability to other agent task domains (summarization, planning, data analysis) not validated.

2. **Vendor Selection**: 4 agents analyzed. Other major agents (Cursor, Windsurf, Devin) not included due to trace format unavailability at collection time.

3. **Temporal Snapshot**: Collected February 7, 2026. Agent formats may evolve; this schema reflects 2026-02-07 implementations.

4. **Success Bias**: Dataset includes both successful (78%+) and failed attempts, but failed attempts may underrepresent certain edge cases (e.g., very long sessions, multi-file complex refactors).

## Reproduction

To regenerate this dataset:

```bash
# XOR monorepo (not included in this repository)
cd /path/to/xor
python -m bench.cli run-arvo \
  --agents claude,gemini,codex,opencode \
  --dataset arvo-250iq \
  --output bench/runs/arvo-250iq/run-$(date +%Y-%m-%d)
```

## Cross-References

- **I-D Appendix B**: [Empirical Basis](../draft-birkholz-verifiable-agent-conversations.md#appendix-b-empirical-basis)
- **Extraction Methodology**: [docs/cddl-extraction-methodology.md](../docs/cddl-extraction-methodology.md)
- **Agent Type Mapping**: [docs/agent-type-mapping-table.md](../docs/agent-type-mapping-table.md)
- **CDDL Schema**: [agent-conversation.cddl](../agent-conversation.cddl)
- **Reasoning Artifacts**: [examples/reasoning-artifacts/](../examples/reasoning-artifacts/)

---

**Note**: This manifest documents the empirical dataset used to derive the CDDL schema. The actual trace files are not included in this repository due to size constraints (671 files, ~1.2GB total). Representative samples are provided in `examples/traces/`.
