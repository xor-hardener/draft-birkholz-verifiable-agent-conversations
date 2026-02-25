# Agent Trace Format Samples

<!-- See: ../../agent-conversation.cddl for the unified schema -->
<!-- See: ../../docs/agent-type-mapping-table.md for detailed mapping -->
<!-- See: ../DATASET_MANIFEST.md for the full empirical dataset -->

These are minimal representative samples showing the message structure from each of the 4 agent implementations analyzed in the CVE-Bench "arvo-250iq" dataset.

## Sample Files

| File | Agent | Format | Lines | Description |
|:-----|:------|:-------|:------|:------------|
| `claude-sample.jsonl` | Claude Code | JSONL (one object/line) | 5 | User message, assistant response with tool call, tool result |
| `gemini-sample.json` | Gemini CLI | Single JSON array | ~30 | Array of message objects with function calls |
| `codex-sample.json` | Codex CLI | JSONL with envelope | ~20 | Response items with metadata wrapper |
| `opencode-sample.json` | OpenCode | Single JSON with metadata | ~40 | Session with metadata envelope |

## Key Differences Illustrated

### 1. File Format

- **Claude Code**: JSONL (newline-delimited JSON objects)
- **Gemini CLI**: Single JSON array
- **Codex CLI**: JSONL with response_item wrapping
- **OpenCode**: Single JSON object with session metadata

### 2. Timestamp Format

- **Claude/Gemini/Codex**: RFC 3339 strings (`"2026-02-07T11:22:22.551Z"`)
- **OpenCode**: Epoch milliseconds (`1707307336344`)

**CDDL Abstraction**: `abstract-timestamp = tstr / number`

### 3. Tool Call Representation

- **Claude Code**: `content[].type: "tool_use"` with `id`, `name`, `input`
- **Gemini CLI**: `parts[].function_call` with `name`, `args`
- **Codex CLI**: `content[].type: "function_call"` with `function`, `arguments`
- **OpenCode**: `tool_calls[]` with `id`, `type`, `function`

**CDDL Abstraction**: `tool-call-entry` with semantic mapping

### 4. Reasoning/Thinking

- **Claude Code**: Explicit `content[].type: "thinking"` entries
- **Gemini CLI**: No explicit reasoning (embedded in text)
- **Codex CLI**: `content[].type: "reasoning"` entries
- **OpenCode**: No explicit reasoning (embedded in text)

**CDDL Abstraction**: Optional `reasoning-entry` (50% of agents support)

## Abstraction Process

These samples were used in the 4-stage extraction pipeline:

1. **RLM Extraction** → Identified common patterns across 4 formats
2. **Agent0 Questions** → Generated 12 probing questions about variance
3. **Quint Decision** → Evidence-backed schema decisions (0.80 confidence)
4. **Council Deliberation** → Multi-perspective validation (0.71 consensus)

See [docs/cddl-extraction-methodology.md](../../docs/cddl-extraction-methodology.md) for full details.

## Usage

These samples are intended for:

1. **Schema Validation**: Test CDDL validators against known agent formats
2. **Conversion Reference**: Implement vendor-specific to abstract type converters
3. **Documentation**: Understand concrete format differences that motivated abstractions

## Full Dataset Access

These are minimal samples (5-40 lines each). The full dataset contains:

- **221 complete session traces** (13-300+ events each)
- **23 CVEs** across 3 projects (harfbuzz, openthread, rawspeed)
- **671 total files** (~1.2GB) including patches and metadata

See [../DATASET_MANIFEST.md](../DATASET_MANIFEST.md) for complete inventory.

Full dataset location: `bench/runs/arvo-250iq/run-2026-02-07/` (XOR monorepo, not included in this repository)

## Cross-References

- **CDDL Schema**: [agent-conversation.cddl](../../agent-conversation.cddl)
- **Agent Type Mapping**: [docs/agent-type-mapping-table.md](../../docs/agent-type-mapping-table.md)
- **I-D Appendix C** (Test Vectors): [draft-birkholz-verifiable-agent-conversations.md#appendix-c](../../draft-birkholz-verifiable-agent-conversations.md#appendix-c-test-vectors)
