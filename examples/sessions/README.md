# Example Sessions

One raw session per agent-model combination from the ARVO-136 benchmark dataset.
Used by `scripts/validate-sessions.py` for CDDL schema validation.

Sessions were selected for diversity of tool usage, conversation depth, and
representativeness — not file size. See "Selection criteria" and "Previously
selected (largest)" below for rationale.

## Source files

| Simplified name | Original benchmark filename | Size | Why picked |
|---|---|---|---|
| `claude-opus-4-5.jsonl` | `claude-claude-opus-4-5-blosc-XOR-c-blosc2-ID-24837-0-session.jsonl` | 1.8M | 7 distinct tools (133 calls), 11 edits, 13 web research calls |
| `claude-opus-4-6.jsonl` | `claude-claude-opus-4-6-envoyproxy-XOR-envoy-ID-32878-0-session.jsonl` | 958K | 8 distinct tools (146 calls), uses Task + TodoWrite planning |
| `codex-gpt-5-2.jsonl` | `codex-gpt-5.2-python-XOR-cpython-ID-58295-0-session.jsonl` | 937K | 4 tool types, 97 reasoning blocks, iterative patching |
| `codex-gpt-5-2-codex.jsonl` | `codex-gpt-5.2-codex-bellard-XOR-quickjs-ID-65393-0-session.jsonl` | 1.1M | 4 tool types + web_search (7 distinct item types) |
| `cursor-composer-1-5.jsonl` | `cursor-composer-1.5-libarchive-XOR-libarchive-ID-11196-0-session.jsonl` | 16K | Best substantive text density in combo (16 assistant turns, avg 394 chars) |
| `cursor-gpt-5-2.jsonl` | `cursor-gpt-5.2-blosc-XOR-c-blosc2-ID-24837-0-session.jsonl` | 30K | Highest avg assistant text (1,266 chars/turn), systematic approach |
| `cursor-gpt-5-3-codex.jsonl` | `cursor-gpt-5.3-codex-harfbuzz-XOR-harfbuzz-ID-10097-0-session.jsonl` | 15K | Best substantive-text-per-turn ratio, clear reasoning chain |
| `cursor-opus-4-6.jsonl` | `cursor-opus-4.6-osgeo-XOR-gdal-ID-10637-0-session.jsonl` | 58K | 79 lines, 77 substantive text entries showing iterative debugging |
| `gemini-gemini-3-pro-preview.jsonl` | `gemini-gemini-3-pro-preview-blosc-XOR-c-blosc2-ID-29287-0-session.jsonl` | 555K | 8 unique tools (39 calls) — highest tool diversity of any Gemini session |
| `opencode-claude-opus-4-5.jsonl` | `opencode-claude-opus-4-5-osgeo-XOR-gdal-ID-10637-0-session.jsonl` | 3.4M | 131 turns, 129 tool calls (6 types), 82 reasoning text blocks |
| `opencode-claude-opus-4-6.jsonl` | `opencode-claude-opus-4-6-open-source-parsers-XOR-jsoncpp-ID-18140-0-session.jsonl` | 3.2M | 200 tool calls (8 types incl. todowrite + webfetch), 199 turns |
| `opencode-gpt-5-2.jsonl` | `opencode-gpt-5.2-cesanta-XOR-mongoose-ID-53029-0-session.jsonl` | 3.7M | 7 tools, 196 reasoning blocks, includes webfetch |
| `opencode-gpt-5-2-codex.jsonl` | `opencode-gpt-5.2-codex-libjxl-XOR-libjxl-ID-49277-0-session.jsonl` | 3.2M | 7 tools (150 calls), 142 turns, uses todowrite planning |

## Selection criteria

Sessions were picked to maximize:
- **Tool diversity** — sessions using the widest variety of tools (edits, search, web fetch, task planning)
- **Conversation depth** — multiple turns of reasoning, not just a single prompt/response
- **Representativeness** — typical session structure for each agent, not outliers
- **Project diversity** — different OSS projects across the 13 picks where possible

## Size breakdown (~19MB total)

Actual conversation content (assistant text + user messages) accounts for only
~14% of the total size. The rest is tool output and structural overhead:

| Category | Size | % | What it contains |
|---|---|---|---|
| Tool output/results | 8.8M | 48% | grep/read results, command stdout, file diffs |
| -- embedded file content | 5.0M | 27% | `originalFile`, `filediff` — full source file snapshots inside tool results |
| Metadata/structure | 7.1M | 38% | UUIDs, timestamps, session IDs, step markers, JSON keys, token usage stats |
| Assistant text/reasoning | 2.3M | 12% | Model-generated output + chain-of-thought reasoning |
| User messages | 0.3M | 2% | Task prompts and system instructions |

This is inherent to how each agent stores sessions:

- **Claude Code** stores `toolUseResult.originalFile` — a full copy of every file
  read or edited. In `claude-opus-4-5.jsonl`, tool output is 83% of the file.
- **OpenCode** stores `state.metadata.filediff` — complete before/after snapshots
  for every edit. In `opencode-claude-opus-4-5.jsonl`, embedded file content alone
  is 52% of the file.
- **Codex CLI** repeats `turn_context` (full system instructions) between every
  turn, inflating metadata to 44-56% of each file.
- **Gemini CLI** stores full tool call results inline (70% tool output).
- **Cursor** files are tiny (120KB total across 4 files) because Cursor stores no
  tool results, no metadata — just bare `{role, message}` text.

## Previously selected (largest)

The original selection picked the largest file per agent-model combo. Those turned
out to be dominated by bloated tool output rather than interesting conversations:

| Simplified name | Original benchmark filename | Size | Problem |
|---|---|---|---|
| `claude-opus-4-5.jsonl` | `claude-claude-opus-4-5-cesanta-XOR-mongoose-ID-53029-0-session.jsonl` | 69M | Single line with 67MB raw `git diff` stdout stored in `toolUseResult` |
| `claude-opus-4-6.jsonl` | `claude-claude-opus-4-6-bellard-XOR-quickjs-ID-65386-0-session.jsonl` | 2.1M | 1.8MB `originalFile` snapshot from one edit tool result |
| `codex-gpt-5-2.jsonl` | `codex-gpt-5.2-wireshark-XOR-wireshark-ID-10162-0-session.jsonl` | 1.7M | Large but only 5 response items — size from tool output bulk |
| `codex-gpt-5-2-codex.jsonl` | `codex-gpt-5.2-codex-envoyproxy-XOR-envoy-ID-26834-0-session.jsonl` | 4.7M | Same — few entries, inflated by tool output |
| `cursor-composer-1-5.jsonl` | (same as current) | 16K | Kept — best option in combo |
| `cursor-gpt-5-2.jsonl` | (same as current) | 30K | Kept — best option in combo |
| `cursor-gpt-5-3-codex.jsonl` | `cursor-gpt-5.3-codex-harfbuzz-XOR-harfbuzz-ID-11081-0-session.jsonl` | 16K | 40 lines but many short "thinking" turns with low text density |
| `cursor-opus-4-6.jsonl` | `cursor-opus-4.6-google-XOR-flatbuffers-ID-38778-0-session.jsonl` | 136K | Usable but less diverse project coverage than current pick |
| `gemini-gemini-3-pro-preview.jsonl` | `gemini-gemini-3-pro-preview-openvswitch-XOR-ovs-ID-11408-0-session.jsonl` | 924K | Only 5 distinct tools vs 8 in current pick |
| `opencode-claude-opus-4-5.jsonl` | `opencode-claude-opus-4-5-libjxl-XOR-libjxl-ID-49277-0-session.jsonl` | 22M | Bloated by full before/after file snapshots in edit `filediff` |
| `opencode-claude-opus-4-6.jsonl` | `opencode-claude-opus-4-6-libredwg-XOR-libredwg-ID-54380-0-session.jsonl` | 44M | 12MB edit filediffs + 14MB duplicated diffs in state snapshots |
| `opencode-gpt-5-2.jsonl` | `opencode-gpt-5.2-harfbuzz-XOR-harfbuzz-ID-12241-0-session.jsonl` | 6.4M | Fewer tools (5) and reasoning blocks than current pick |
| `opencode-gpt-5-2-codex.jsonl` | `opencode-gpt-5.2-codex-libarchive-XOR-libarchive-ID-38751-0-session.jsonl` | 18M | Bloated — fewer tool types and turns than current pick |
