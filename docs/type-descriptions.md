# Type Descriptions for Verifiable Agent Conversations

This document provides detailed descriptions of each data type defined in the
CDDL schema (`agent-conversation.cddl`). Each section covers a single map type
with a purpose statement (3-4 sentences) and per-member descriptions (1-2
sentences each).

Intended for inclusion in the Internet-Draft body text
(`draft-birkholz-verifiable-agent-conversations.md`).

The schema is defined in CDDL (RFC 8610) and validates both JSON and CBOR
serializations. The reference implementation produces JSON as the primary
format and CBOR as an alternative (`--cbor` flag). The COSE_Sign1 signing
envelope (Section 9) uses CBOR natively.

## Field Naming Convention

Entries in a verifiable agent record contain two categories of fields:

- **Canonical fields** use kebab-case naming (e.g., `type`, `content`,
  `call-id`, `model-id`, `parent-id`, `token-usage`, `event-type`). These
  are defined in the CDDL schema and have consistent semantics across all
  agent formats.

- **Native passthrough fields** retain the original naming convention of the
  source agent (e.g., `isSidechain`, `requestId`, `sessionID`,
  `messageID`). These are preserved verbatim via the `* tstr => any`
  extensibility mechanism.

Consumers SHOULD process canonical fields for interoperability and MAY
ignore native passthrough fields. The naming convention itself serves as a
reliable discriminator: kebab-case fields are canonical; camelCase or
snake_case fields are native passthrough.

Null-valued native fields are filtered out during translation. Only fields
with non-null values appear in the output.

## Common Types

### abstract-timestamp

Timestamps appear throughout the schema to record when events occurred.
The schema accepts two representations to accommodate the diversity of agent
implementations: RFC 3339 date-time strings (e.g., `"2026-02-10T17:27:14Z"`)
and numeric epoch milliseconds (e.g., `1739205834496`).
Most agents (Claude Code, Gemini CLI, Codex CLI) emit ISO 8601 / RFC 3339
strings; OpenCode uses epoch milliseconds.
New implementations SHOULD use RFC 3339 strings; consumers MUST accept both
forms.

### session-id

A session identifier is an opaque string that uniquely identifies a
conversation session. Different agent implementations use different ID
schemes: Claude Code and Gemini CLI use UUID v4, Codex CLI uses UUID v7,
and OpenCode uses SHA-256 hashes. New implementations SHOULD use UUID v7
(RFC 9562) for built-in temporal ordering.

### entry-id

An entry identifier is a per-entry unique reference within a session.
Three of five reference agents provide explicit entry IDs; others use
positional indexing or lack IDs entirely. Entry IDs enable parent-child
linking (via `parent-id`) and tool call-result correlation (via `call-id`).

## Root Type

### verifiable-agent-record

The `verifiable-agent-record` is the top-level container for all data
produced by or about an agent conversation. It unifies two complementary
perspectives: the session trace captures HOW code was produced (the full
conversation replay), while file attribution captures WHAT code was produced
(which files were modified and by whom). Neither perspective subsumes the
other; a complete record may contain both.

The root type also carries version metadata for schema evolution and an
optional signing envelope reference for cryptographic verifiability.

Members:

- **version** (`tstr`, required): The schema version string following semantic
  versioning (e.g., `"3.0.0-draft"`). Consumers use this field to select the
  appropriate parser or validation logic.

- **id** (`tstr`, required): A unique identifier for this record, typically a
  UUID v4 or v7. Distinguishes records when multiple are stored or transmitted
  together.

- **created** (`abstract-timestamp`, optional): The timestamp when this record
  was generated. Distinct from session timestamps, which record when the
  conversation occurred.

- **session** (`session-trace`, required): The full conversation trace
  including all entries, tool calls, reasoning steps, and system events.
  This is the primary recording format.

- **file-attribution** (`file-attribution-record`, optional): Structured data
  about which files were modified and which line ranges were written by the
  agent. Can be partially derived from the session trace by analyzing
  file-modifying tool calls.

- **vcs** (`vcs-context`, optional): Version control metadata at the record
  level (repository, branch, revision). Provides reproducibility context.

- **recording-agent** (`recording-agent`, optional): Identifies the tool or
  agent that generated this record (as opposed to the agent that conducted
  the conversation).

- **\* tstr => any** (extensibility): Allows additional fields without schema
  changes, following the extensibility pattern from RFC 9052 (COSE).

## Session Types

### session-trace

A `session-trace` captures the full conversation between a user and an
autonomous agent. It contains an ordered array of entries representing
messages, tool invocations, reasoning steps, and system events. The trace
preserves the complete interaction history including all native agent
metadata, enabling both replay and audit of the conversation.

In version 3 of this schema, the previous distinction between "interactive"
and "autonomous" session types was removed. All sessions use this single
type, with an optional `format` field for classification when needed.

Members:

- **format** (`tstr`, optional): Classifies the session style, such as
  `"interactive"` (human-in-the-loop) or `"autonomous"` (fully automated).
  Informative only; does not change the structure.

- **session-id** (`session-id`, required): Unique identifier for this session.
  Four of five reference agents natively provide session identifiers.

- **session-start** (`abstract-timestamp`, optional): When the session began.
  Four of five agents provide start timestamps; Cursor lacks timestamps.

- **session-end** (`abstract-timestamp`, optional): When the session ended.
  Same coverage as `session-start`.

- **agent-meta** (`agent-meta`, required): Metadata about the agent and model
  that conducted this conversation. Required because agent identification is
  fundamental to provenance.

- **environment** (`environment`, optional): Execution environment context
  such as working directory and version control state. Three of five agents
  provide this data.

- **entries** (`[* entry]`, required): The ordered array of conversation
  entries. This is the core content of the session trace.

### agent-meta

The `agent-meta` type identifies the coding agent and language model used
during a conversation session. Agent identification is essential for
provenance tracking: knowing which model produced which output enables
auditing, capability assessment, and compliance verification. Four of five
reference agents provide model identification natively; when unavailable
(as with Cursor), the converter sets the model to `"unknown"`.

For multi-model sessions where different entries may use different models,
the `models` array lists all models used, while `model-id` identifies the
primary model.

Members:

- **model-id** (`tstr`, required): The primary language model identifier, using
  the naming convention of the provider (e.g., `"claude-opus-4-5-20251101"`,
  `"gemini-2.0-flash"`). Required even when the model is unknown.

- **model-provider** (`tstr`, required): The provider of the primary model
  (e.g., `"anthropic"`, `"google"`, `"openai"`). Together with `model-id`,
  this uniquely identifies the model.

- **models** (`[* tstr]`, optional): List of all model identifiers used during
  the session. Relevant for multi-model sessions where the agent switches
  between models.

- **cli-name** (`tstr`, optional): The name of the CLI tool or agent framework
  (e.g., `"claude-code"`, `"gemini-cli"`, `"codex-cli"`).

- **cli-version** (`tstr`, optional): The version of the CLI tool. Two of five
  reference agents provide this field.

### recording-agent

The `recording-agent` identifies the tool that GENERATED this verifiable
agent record, as distinct from the agent that conducted the conversation.
For example, the conversation may have been conducted by Claude Code, but
the record was generated by `vac-validate` (the reference parser). This
distinction matters for provenance chains: the recording tool's version
affects how native data is translated into the canonical schema. The
reference implementation sets this to `{name: "vac-validate", version:
"3.0.0-draft"}`.

Members:

- **name** (`tstr`, required): The name of the recording tool or agent.

- **version** (`tstr`, optional): The version of the recording tool.

## Environment Types

### environment

The `environment` type captures execution context for the conversation:
where the agent was running, what version control state was active, and
whether sandboxing was in effect. This context is important for
reproducibility and for understanding the scope of file modifications.
Three of five reference agents provide working directory information.

Members:

- **working-dir** (`tstr`, required): The primary working directory path.
  File paths in tool calls are typically relative to this directory.

- **vcs** (`vcs-context`, optional): Version control state at the time of
  the session (branch, revision, etc.).

- **sandboxes** (`[* tstr]`, optional): Paths to sandbox mount points.
  Some agents (OpenCode, Codex) run in sandboxed environments where the
  working directory is a temporary mount.

### vcs-context

The `vcs-context` type captures version control metadata for
reproducibility. Knowing the exact repository, branch, and commit at the
time of a conversation enables consumers to reconstruct the codebase state
and verify file attributions. This type appears both at the environment
level (session context) and at the record level (record-time context).

Members:

- **type** (`tstr`, required): The version control system type (e.g.,
  `"git"`, `"jj"`, `"hg"`, `"svn"`). Git is overwhelmingly dominant in
  current agent implementations.

- **revision** (`tstr`, optional): The commit SHA or change identifier at
  session time.

- **branch** (`tstr`, optional): The active branch name. Two of four
  VCS-aware agents provide this.

- **repository** (`tstr`, optional): The repository URL. One of four agents
  provides this, but it is valuable for cross-referencing.

## Entry Types

The schema defines five entry types. Each type uses a `type` field as the
discriminator. All entry types support optional `children` for hierarchical
nesting (used by Claude Code and Gemini CLI to represent sub-entries within
a parent message) and `* tstr => any` for preserving native agent fields
that do not map to canonical fields.

### entry (union)

An `entry` is the union of all five entry types: `message-entry`,
`tool-call-entry`, `tool-result-entry`, `reasoning-entry`, and
`event-entry`. The `type` field value determines which variant applies.
This union type is used in the `entries` array of `session-trace` and in
the `children` array of any entry, enabling recursive nesting.

### message-entry

A `message-entry` represents a conversational turn: either human input
(`type: "user"`) or agent response (`type: "assistant"`). This is the most
common entry type, carrying the primary dialogue content of a session.
All five reference agent formats have user and assistant messages, making
this the most universally supported entry type.

For assistant messages, additional metadata may be present: the model
that generated the response, the reason the generation stopped, and token
usage statistics. These fields are absent on user messages, which is why
they are marked optional despite having strong vendor support on assistant
entries.

Members:

- **type** (`"user"` / `"assistant"`, required): The message direction.
  `"user"` indicates human (or upstream agent) input; `"assistant"` indicates
  the agent's response.

- **content** (`any`, optional): The message body. The type varies by agent:
  plain text strings (Gemini CLI, OpenCode), arrays of typed content parts
  preserving native structure (Claude Code, Cursor, Codex CLI), or absent
  when the agent places content exclusively in child entries (OpenCode
  message-level envelopes). The schema intentionally allows `any` to
  preserve native fidelity. Consumers SHOULD handle at minimum `tstr` and
  `[* any]` (array of content blocks).

- **timestamp** (`abstract-timestamp`, optional): When this message was
  produced. Four of five agents provide timestamps.

- **id** (`entry-id`, optional): Unique identifier for this entry within
  the session. Enables parent-child references.

- **model-id** (`tstr`, optional): The model that generated this response.
  Present on assistant entries (four of five agents); absent on user entries.

- **parent-id** (`entry-id`, optional): References the parent entry, enabling
  tree-structured conversations. Two of five agents (Claude Code, OpenCode)
  use this for branching or sidechain support.

- **token-usage** (`token-usage`, optional): Token consumption metrics for
  this response. See `token-usage` type description below.

- **children** (`[* entry]`, optional): Nested entries within this message.
  Used when the native format embeds tool calls or reasoning blocks inside
  an assistant message (Claude Code, Gemini CLI).

### tool-call-entry

A `tool-call-entry` represents a tool invocation: which tool was called and
with what arguments. Tool calls are central to agent conversation records
because tool use is the primary mechanism by which agents interact with the
external environment: reading files, executing commands, searching
codebases, and modifying source code. All five reference agents record
tool calls, though the native representations vary significantly.

Members:

- **type** (`"tool-call"`, required): Fixed discriminator value.

- **name** (`tstr`, required): The tool name (e.g., `"Bash"`, `"Edit"`,
  `"Read"`, `"apply_patch"`). Present across all five reference agents.

- **input** (`any`, required): The arguments passed to the tool, preserved
  in their native structure (typically a JSON object).

- **call-id** (`tstr`, optional): Links this call to its corresponding
  result. Three of five agents provide explicit call IDs; the others use
  positional correlation.

- **timestamp** (`abstract-timestamp`, optional): When this tool call
  occurred.

- **id** (`entry-id`, optional): Unique identifier for this entry.

- **children** (`[* entry]`, optional): Nested entries (rare for tool calls
  but supported for consistency).

### tool-result-entry

A `tool-result-entry` represents the output returned by a tool after
execution. It is linked to its corresponding `tool-call-entry` via the
`call-id` field. The result carries the tool's response data and optional
status metadata indicating success or failure.

Members:

- **type** (`"tool-result"`, required): Fixed discriminator value.

- **output** (`any`, required): The tool's response, preserved in native
  structure. All five reference agents provide tool output.

- **call-id** (`tstr`, optional): Links this result to its corresponding
  call. Three of five agents provide explicit call IDs.

- **status** (`tstr`, optional): Outcome status of the tool execution, such
  as `"success"`, `"error"`, or `"completed"`. Three of five agents provide
  this field.

- **is-error** (`bool`, optional): Boolean error flag, present when the tool
  execution failed.

- **timestamp** (`abstract-timestamp`, optional): When this tool result was
  returned.

- **id** (`entry-id`, optional): Unique identifier for this entry.

- **children** (`[* entry]`, optional): Nested entries (rare for tool results
  but supported for consistency).

### reasoning-entry

A `reasoning-entry` captures chain-of-thought, thinking, or internal
reasoning content from the agent. Not all agents expose reasoning traces;
when they do, the content may be plaintext, structured blocks, or encrypted
(as with some model providers that protect reasoning content). Reasoning
entries are valuable for auditing decision-making processes and understanding
why an agent took particular actions.

Members:

- **type** (`"reasoning"`, required): Fixed discriminator value.

- **content** (`any`, required): The reasoning text or structured content.
  May be an empty string when only encrypted content is available (the model
  provider exposes the existence of reasoning but not its content).

- **encrypted** (`tstr`, optional): Encrypted reasoning content. Used by
  Codex CLI where the model provider encrypts chain-of-thought output.

- **subject** (`tstr`, optional): A topic label for the reasoning block.
  Used by Gemini CLI's "thought" entries to categorize thinking.

- **timestamp** (`abstract-timestamp`, optional): When this reasoning was
  produced.

- **id** (`entry-id`, optional): Unique identifier for this entry.

- **children** (`[* entry]`, optional): Nested entries within the reasoning
  block.

### event-entry

An `event-entry` records system lifecycle events that are not part of the
conversation dialogue but are relevant for understanding the session context.
Examples include session start/end markers, token usage summaries, permission
changes, and configuration events. These events provide the operational
metadata that surrounds the actual conversation, enabling analysis of
session structure, resource consumption, and agent behavior patterns.

Members:

- **type** (`"system-event"`, required): Fixed discriminator value.

- **event-type** (`tstr`, required): Classifies the event, such as
  `"session-start"`, `"session-end"`, `"token-count"`, `"permission-change"`,
  or `"queue-operation"`. The values are not enumerated in the schema to
  accommodate vendor-specific event types.

- **data** (`{ * tstr => any }`, optional): Event-specific payload. The
  structure varies by event type; for example, a `"token-count"` event
  might carry input and output token counts.

- **timestamp** (`abstract-timestamp`, optional): When this event occurred.

- **id** (`entry-id`, optional): Unique identifier for this entry.

- **children** (`[* entry]`, optional): Nested entries (rare for events but
  supported for consistency).

## Token Usage

### token-usage

The `token-usage` type captures token consumption metrics for a model
response. Token usage data is essential for cost tracking, quota management,
and understanding model behavior (e.g., how much context was used, whether
caching was effective). Four of five reference agents provide token data in
varying native formats; the parsers normalize these into the canonical fields
defined here.

Members:

- **input** (`uint`, optional): The number of input tokens consumed by this
  response. Four of five agents provide this metric.

- **output** (`uint`, optional): The number of output tokens generated.
  Four of five agents provide this.

- **cached** (`uint`, optional): The number of input tokens served from cache
  rather than reprocessed. Three of five agents report cached tokens.

- **reasoning** (`uint`, optional): Tokens consumed by chain-of-thought or
  reasoning computation. Two of five agents report this separately.

- **total** (`uint`, optional): The total token count (may differ from
  input + output when reasoning or cached tokens are counted separately).
  Two of five agents provide a pre-computed total.

- **cost** (`number`, optional): The monetary cost in US dollars for this
  response. One of five agents (OpenCode) tracks cost natively.

Agent-specific native fields are preserved alongside canonical fields via
`* tstr => any`. Examples include `cache_creation_input_tokens` and
`service_tier` (Claude Code), `thoughts` and `tool` token counts (Gemini
CLI), `cache` read/write counts (OpenCode), and `total_token_usage` objects
(Codex CLI). Consumers SHOULD use the canonical fields for cross-agent
comparisons and MAY use native fields for agent-specific analysis.

## File Attribution Types

> **NOTE:** This section is specified but not yet validated against real
> session data. Derivability analysis (4/5 agents) is documented in
> `docs/reviews/2026-02-18/file-attribution-investigation.md`.
> Implementation is pending.

File attribution captures WHAT code was produced: which files were modified,
which line ranges were changed, and who (human or AI) authored them. Four of
five reference agents provide sufficient data to derive file attributions
from session traces.

### file-attribution-record

The `file-attribution-record` is the top-level container for file
attribution data. It holds an array of files, each with their attributed
line ranges and contributor information. This record can exist alongside a
session trace (providing complementary WHAT vs HOW perspectives) or
independently when only the file attribution is needed.

Members:

- **files** (`[* file]`, required): Array of files with attributed ranges.

### file

A `file` represents a single source file that was modified during the
conversation. It groups all conversations (sessions) that contributed
changes to this file, enabling multi-session attribution tracking.

Members:

- **path** (`tstr`, required): The file path relative to the repository root.

- **conversations** (`[* conversation]`, required): The conversations that
  contributed modifications to this file.

### conversation

A `conversation` links a specific session to the line ranges it produced
in a file. This enables tracing from a line of code back to the
conversation that generated it, supporting audit and provenance workflows.

Members:

- **url** (`tstr`, optional): A URL pointing to the conversation source
  (e.g., a web UI permalink). Not derivable from session data; must be
  supplied externally.

- **contributor** (`contributor`, optional): The default contributor for
  all ranges in this conversation. Can be overridden per-range.

- **ranges** (`[* range]`, required): The line ranges in the file that
  were produced by this conversation.

- **related** (`[* resource]`, optional): External resources related to
  this conversation (e.g., issue trackers, documentation).

### range

A `range` identifies a contiguous block of lines in a file that were
produced by a specific conversation. Line numbers are 1-indexed and
inclusive. The optional content hash enables position-independent tracking:
if lines move due to later edits, the hash can re-locate the content.

Members:

- **start-line** (`uint`, required): The first line of the range (1-indexed).

- **end-line** (`uint`, required): The last line of the range (1-indexed,
  inclusive).

- **content-hash** (`tstr`, optional): A hash of the range content for
  position-independent identification.

- **content-hash-alg** (`tstr`, optional): The hash algorithm used
  (default: `"sha-256"`).

- **contributor** (`contributor`, optional): Overrides the conversation-level
  contributor for this specific range.

### contributor

A `contributor` identifies who authored a range of code. The `type` field
distinguishes between human-authored, AI-generated, mixed, and unknown
authorship. For AI-generated code, the `model_id` field identifies the
specific model, enabling per-model attribution in multi-model sessions.

Members:

- **type** (`"human"` / `"ai"` / `"mixed"` / `"unknown"`, required):
  The authorship category.

- **model-id** (`tstr`, optional): The model identifier for AI-authored
  ranges, following the models.dev naming convention.

### resource

A `resource` represents an external reference related to a conversation,
such as an issue tracker entry, a pull request, or a documentation page.

Members:

- **type** (`tstr`, required): The resource type (e.g., `"issue"`, `"pr"`,
  `"documentation"`).

- **url** (`tstr`, required): The URL of the resource.

## Signing Envelope Types

### signed-agent-record

The `signed-agent-record` is a COSE_Sign1 envelope (RFC 9052, CBOR Tag 18)
that wraps a verifiable agent record with a cryptographic signature.
Signing is the mechanism that provides non-repudiation and tamper evidence,
satisfying the RATS evidence generation (RFC 9334) and SCITT auditability
requirements. The signing envelope is independent of schema compliance: a
record can be signed regardless of whether it conforms to the canonical
schema.

The reference implementation uses Ed25519 (EdDSA) with detached payloads,
meaning the JSON record file remains separate from the signature file.
This enables independent inspection and diff of the payload while the
compact signature file (~300 bytes) provides verifiability.

Members (COSE_Sign1 array elements):

- **protected** (`bstr`, required): The serialized protected header
  containing the algorithm identifier and content type. For the reference
  implementation: `{1: -8, 3: "application/json"}` (algorithm EdDSA,
  content type JSON).

- **unprotected** (`{ ? 100 => trace-metadata }`, required): The unprotected
  header carrying trace metadata at label 100. Unprotected because this
  metadata is informational and does not need integrity protection beyond
  what the signature already provides over the payload.

- **payload** (`bstr / null`, required): The serialized record bytes, or
  `null` for detached payloads. In detached mode, the payload is supplied
  separately during verification.

- **signature** (`bstr`, required): The cryptographic signature over the
  protected header and payload.

### trace-metadata

The `trace-metadata` type carries summary information about the signed
record in the COSE_Sign1 unprotected header. This enables consumers to
inspect key properties of a signed record (session ID, agent, timestamps)
without deserializing the full payload. Particularly useful for indexing
and routing in transparency log systems (SCITT).

Members:

- **session-id** (`session-id`, required): The session identifier from
  the signed record.

- **agent-vendor** (`tstr`, required): The agent provider name (e.g.,
  `"anthropic"`, `"google"`).

- **trace-format** (`trace-format-id`, required): Identifies the format
  of the signed payload (e.g., `"ietf-vac-v3.0"` for canonical records
  or `"claude-jsonl"` for native format).

- **timestamp-start** (`abstract-timestamp`, required): When the session
  began.

- **timestamp-end** (`abstract-timestamp`, optional): When the session
  ended.

- **content-hash** (`tstr`, optional): SHA-256 hex digest of the payload
  bytes, enabling integrity checking independent of the COSE signature.

- **content-hash-alg** (`tstr`, optional): The hash algorithm used
  (default: `"sha-256"`).

### trace-format-id

The `trace-format-id` identifies the serialization format of the payload
in a signed record. Defined as `tstr` to allow any format identifier.
Known values include: `"ietf-vac-v3.0"` (canonical schema), `"claude-jsonl"`,
`"gemini-json"`, `"codex-jsonl"`, `"opencode-json"`, `"cursor-jsonl"`
(native formats signed without translation). New implementations SHOULD
use the canonical format where possible.
