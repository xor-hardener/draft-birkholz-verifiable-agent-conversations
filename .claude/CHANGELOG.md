# Design Decision Log

Tracks all interview questions asked and decisions made during schema and tooling development.

## 2026-02-16: COSE_Sign1 Signing Implementation

Implemented `scripts/sign-record.py` — a standalone tool that produces cryptographically
signed agent session records using COSE_Sign1 (RFC 9052), matching the `signed-agent-record`
type defined in CDDL Section 11.

### Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | New script or extend validate-sessions.py? | **New standalone `scripts/sign-record.py`** | Separation of concerns: validation ≠ signing. Different dependencies (pycose, cbor2). |
| 2 | Algorithm? | **Ed25519 (EdDSA)** | Fast, small 64-byte signatures, deterministic. Used by RATS/SCITT examples. COSE algorithm ID: -8. |
| 3 | Payload mode? | **Detached only** | COSE_Sign1 with `payload=null`. JSON record file stays separate, can be inspected/diffed. Signature file is small (~300 bytes). |
| 4 | Key format? | **PEM files (PKCS8/SubjectPublicKeyInfo)** | Standard, interoperable. Private key unencrypted for dev use. |
| 5 | Dependencies? | **`requirements.txt` with pycose, cbor2** | No flake.nix changes. Nix dev shell already installs `requirements*.txt`. |
| 6 | Trace-metadata source? | **Extracted from record JSON** | session-id, agent-vendor, timestamps from the verifiable-agent-record structure. Content hash (SHA-256) computed over canonical JSON bytes. |

### Implementation

- **`keygen`**: Generates Ed25519 keypair via `cryptography` library, writes PEM files.
- **`sign`**: Canonicalizes JSON (compact, sorted keys), builds COSE_Sign1 with detached payload,
  stores trace-metadata in unprotected header at label 100 (per CDDL `trace-metadata-key`).
- **`verify`**: Decodes COSE_Sign1, reattaches detached payload, verifies Ed25519 signature,
  checks content-hash integrity.

### Verification

- All 13 session records signed and verified successfully
- CBOR output inspected: Tag 18, 4-element array, protected header `{1: -8, 3: "application/json"}`,
  unprotected header `{100: trace-metadata}`, payload `null`, 64-byte signature
- Structure matches `signed-agent-record` in CDDL Section 11 exactly

## 2026-02-16: Schema Simplification (content: any + children)

Goal: Minimize the translation layer in `validate-sessions.py` by making the CDDL spec
accept native agent formats more directly.

### Round 1: Core Schema Decisions

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Should `content` change from `tstr` to `any`? | **content: any** | Eliminates `_content_to_str()` entirely. Preserves native structured content (arrays of parts, multimodal blocks). Matches existing `input: any` / `output: any` precedent. |
| 2 | Should entries support inline children? | **Yes, add `? children: [* entry]`** | Lets Claude/Gemini keep their hierarchical message structure (tool blocks inside assistant messages) instead of forcing flat entry arrays. |
| 3 | Should the spec accept `role` as alternative to `type`? | **type only** | Keep `type` as sole discriminator. Parsers rename `role` to `type`. |
| 4 | How should the verifiable-agent-record wrapper work? | **Keep as-is** | The multi-level wrapper (verifiable-agent-record > session > entries) stays. Translation must construct it. |

### Round 2: Naming and Structure

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 5 | Accept native type values (function_call, tool_use) alongside canonical? | **Canonical only** | Pick one name and rename everything. Keeps CDDL clean. |
| 6 | Accept native field names as alternatives (call-id / call_id / callID)? | **Canonical kebab-case only** | CDDL convention is kebab-case. Parsers rename from native conventions. |
| 7 | How should children work for Claude's tool_use/tool_result blocks? | **Children as typed entries** | Children must be valid entry types (tool-call-entry, etc.). Parser maps type values but doesn't need to flatten into separate top-level entries. |
| 8 | Support combined tool-round-trip entry (fused call+result)? | **Keep separate call/result** | Require splitting into tool-call + tool-result. OpenCode/Gemini parsers split fused objects. |

### Round 3: Content and Mapping

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 9 | Tool entry type names? | **tool-call / tool-result** | Current names. Hyphenated, explicit direction. |
| 10 | Should parsers pass through native content structures as-is? | **Pass-through** | No `_content_to_str()`. Maximum fidelity. Native arrays stay as arrays. |
| 11 | Claude mapping: 1 entry + children vs N flat entries? | **1 entry + children** | One assistant entry per JSONL line. Tool-use, text, thinking blocks become typed children. |

### Changes Made

**CDDL (`agent-conversation.cddl`):**
- `content: tstr` → `content: any` on user-entry, assistant-entry, reasoning-entry
- Added `? children: [* entry]` to base-entry

**Script (`scripts/validate-sessions.py`):**
- Claude parser: 1 entry per JSONL line with children for tool-call/tool-result/reasoning
- Gemini parser: 1 entry per message with children (140 flat entries → 24 entries + 138 children)
- Removed all `_content_to_str()` calls from parsers (kept for report utility)
- Content/output passed through as native structures
- Report updated to count children

### Impact
- Gemini entry count: 140 → 24 (+ 138 children)
- Claude: same entry count, but tool/reasoning blocks now in children
- Total produced size: 4.68 MB → 5.79 MB (native arrays slightly larger than flattened strings)
- All 13 sessions pass validation with zero data loss

## 2026-02-16: Secrets Scrub (pre-push audit)

GitHub Push Protection blocked the initial push. Full audit of all 13 session files revealed
two categories of embedded secrets.

### Findings

| Severity | Type | Count | Files | Replacement |
|---|---|---|---|---|
| HIGH | GitHub App Installation Tokens (`ghs_`) in `repository_url` | 2 tokens | `codex-gpt-5-2.jsonl`, `codex-gpt-5-2-codex.jsonl` | `x-access-token:<REDACTED>@` |
| MEDIUM | OpenCode session share secrets (UUIDs) | 31 secrets | All 4 `opencode-*.jsonl` files | `"secret": "<REDACTED>"` |

### Details

**Codex `ghs_` tokens:** The Codex CLI records the full git clone URL in `session_meta.payload.git.repository_url`,
including the `x-access-token:ghs_XXXX@github.com` credential used by the benchmark runner. Both Codex session
files had this on line 1. Tokens are likely expired (short-lived installation tokens) but must not be in public repos.

**OpenCode share secrets:** OpenCode emits `{"id": "...", "secret": "uuid", "url": "https://opncd.ai/share/..."}` objects
throughout sessions (on step boundaries). The `secret` field grants access to the shared session URL. 31 distinct UUIDs
found across the 4 OpenCode files.

### Non-findings (verified false positives)
- `secret_manager_`, `Secret::SecretManagerImpl` in Claude sessions → Envoy C++ source code
- `password`, `Authorization`, `credential` in OpenCode sessions → Mongoose HTTP library source code
- `authorization` in Codex sessions → HPACK static table entries (HTTP/2)
- `credential` in OpenCode sessions → GDAL git commit messages
- `AKIA`-like strings → base64-encoded COSE/CBOR content, not AWS keys
- `tokens` fields → token usage metadata (input_tokens, output_tokens), not auth tokens
