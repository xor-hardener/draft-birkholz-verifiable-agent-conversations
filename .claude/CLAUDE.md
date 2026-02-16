# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an IETF Internet-Draft repository for "Verifiable Agent Conversations" (`draft-birkholz-verifiable-agent-conversations`). It defines conversation records for autonomous AI agents that enable long-term preservation of evidentiary value, auditability, and non-repudiation using IETF building blocks (CBOR, CDDL, COSE, JWT/CWT, SCITT).

The draft is authored using the [martinthomson/i-d-template](https://github.com/martinthomson/i-d-template) toolchain, which generates formatted text and HTML from Markdown source.

## Key Files

- `draft-birkholz-verifiable-agent-conversations.md` — The Internet-Draft source (kramdown-rfc Markdown format with YAML front matter)
- `agent-conversation.cddl` — CDDL schema defining the `agent-convo-record` data structure, included into the draft via `{::include agent-conversation.cddl}`
- `scripts/validate-sessions.py` — Parses 5 agent formats and validates against the CDDL schema
- `scripts/sign-record.py` — Signs/verifies agent records with COSE_Sign1 (Ed25519)
- `Makefile` — Delegates to `lib/main.mk` from i-d-template (auto-cloned on first `make`)

## Tracked Documentation (MUST maintain)

Two companion files track the state of the schema and translation layer. **Always read these
at the start of relevant work, and update them when making changes.**

- **`.claude/CHANGELOG.md`** — Design decision log. When making interactive decisions about
  schema design, spec tradeoffs, or tooling choices, record the question, answer, and
  rationale here. Organized by date and topic.

- **`.claude/BREAKDOWN.md`** — Translation layer breakdown. Documents the exact per-agent
  transformations that `validate-sessions.py` performs (direct matches, renames, un-nesting,
  type mapping, structural extraction, dropped fields, fabricated fields). **Update this file
  whenever parsers or the CDDL schema change** — it must reflect the actual current state.

## Build Commands

```sh
make          # Build HTML and TXT outputs (clones i-d-template into lib/ on first run)
make fix-lint # Auto-fix linting issues
```

The build requires [i-d-template dependencies](https://github.com/martinthomson/i-d-template/blob/main/doc/SETUP.md) (xml2rfc, kramdown-rfc, etc.). The `flake.nix` provides a Nix dev shell with Python and tooling.

## Development Environment (Nix)

The project uses a Nix flake for reproducible dev environments. Entering the shell (`nix develop`) sets up Python with linting tools (flake8, mypy, black, isort), creates a `.venv`, and installs any `requirements*.txt` files.

## Architecture Notes

- The draft uses **kramdown-rfc** Markdown format — YAML front matter defines metadata, references, and authors; the body uses RFC-specific markup like `{{-rats-arch}}` for reference citations and `{::include ...}` for file inclusion.
- The CDDL schema in `agent-conversation.cddl` is the canonical data model definition. Changes to the data model should be made there; the draft includes it automatically.
- The data model centers on `verifiable-agent-record` which contains: version, id, optional session-trace (with entries array), optional file-attribution, optional VCS context, and extensible vendor metadata. Entry types: user, assistant, tool-call, tool-result, reasoning, system-event, vendor. Entries support `children` for nested structures.
- CI uses `martinthomson/i-d-template@v1` GitHub Actions to build, lint, publish to GitHub Pages, and upload tagged versions to the IETF Datatracker.

## Validation Script

```sh
python3 scripts/validate-sessions.py              # validate all sessions
python3 scripts/validate-sessions.py --report      # detailed analysis with data coverage
python3 scripts/validate-sessions.py --dump-dir /tmp/vac-produced  # write produced records
```

- Uses `ruff` for formatting (line-length 121, config in `ruff.toml`)

## Signing Script

```sh
# Generate Ed25519 keypair
python3 scripts/sign-record.py keygen --out /tmp/vac-keys/

# Sign a record (detached COSE_Sign1 payload)
python3 scripts/sign-record.py sign \
  --key /tmp/vac-keys/signing-key.pem \
  --record /tmp/vac-produced/claude-opus-4-6.spec.json \
  --out /tmp/vac-produced/claude-opus-4-6.sig.cbor

# Verify a signature
python3 scripts/sign-record.py verify \
  --key /tmp/vac-keys/signing-key.pub.pem \
  --sig /tmp/vac-produced/claude-opus-4-6.sig.cbor \
  --record /tmp/vac-produced/claude-opus-4-6.spec.json
```

- Produces `signed-agent-record` per CDDL Section 11 (COSE_Sign1, Tag 18)
- Algorithm: Ed25519 (EdDSA), detached payload mode
- Trace-metadata in unprotected header at label 100
- Dependencies: `pycose`, `cbor2` (see `requirements.txt`)

## Conventions

- EditorConfig enforces UTF-8, final newlines, and trimmed trailing whitespace for `.md`, `.xml`, and `.org` files.
- All contributions are subject to IETF IPR policies (BCP 78/79). See `CONTRIBUTING.md`.
- Upstream repo: `github.com/xor-hardener/draft-birkholz-verifiable-agent-conversations`
- **Never stage, commit, or push without explicit user instructions.**
