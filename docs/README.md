# Documentation Index

Companion documentation for the `draft-birkholz-verifiable-agent-conversations` Internet-Draft.

## Specification

- [**type-descriptions.md**](type-descriptions.md) — Detailed descriptions of every CDDL
  map type (3-4 sentences per type, 1-2 per member). Raw markdown for the I-D body text.

## Process

- [**CHANGELOG.md**](CHANGELOG.md) — Design decision log. Records all schema design,
  spec tradeoff, and tooling decisions with rationale.
- [**BREAKDOWN.md**](BREAKDOWN.md) — Translation layer breakdown. Documents the exact
  per-agent transformations that `validate-sessions.py` performs.

## Per-Agent Translation Breakdowns

Each file documents the transformation rules and native JSON schema for one agent format.

- [Claude Code](breakdown/claude-code.md) — JSONL, one event per line
- [Gemini CLI](breakdown/gemini-cli.md) — Single JSON object with `messages[]`
- [Codex CLI](breakdown/codex-cli.md) — JSONL with `{timestamp, type, payload}` envelope
- [OpenCode](breakdown/opencode.md) — Concatenated pretty-printed JSON objects
- [Cursor](breakdown/cursor.md) — Bare JSONL `{role, message}`

## Design Reviews

- [reviews/2026-02-18/simplification-plan.md](reviews/2026-02-18/simplification-plan.md) —
  v3.0.0-draft schema simplification plan (8 decisions, 5 phases)
- [reviews/2026-02-18/original-assessment.md](reviews/2026-02-18/original-assessment.md) —
  Approach B assessment with schema, parser analysis, and consumer use cases
- [reviews/2026-02-18/file-attribution-investigation.md](reviews/2026-02-18/file-attribution-investigation.md) —
  File attribution derivability analysis (Claude Code vs OpenCode)
