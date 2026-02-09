---
v: 3

title: "Verifiable Agent Conversations"
abbrev: "VAC"
docname: draft-birkholz-verifiable-agent-conversations-latest
category: std
consensus: true
submissionType: IETF

ipr: trust200902
area: "Security"
keyword: [ verifiable, evidence, transparency, compliance, auditability ]

stand_alone: yes
smart_quotes: no
pi: [toc, sortrefs, symrefs]

author:
 - name: Henk Birkholz
   email: henk.birkholz@ietf.contact
 - name: Tobias Heldt
   email: tobias@xor.tech

normative:
  RFC3339: datetime
  STD90:
    -: json
    =: RFC8259
  RFC8610: cddl
  STD94:
    -: cbor
    =: RFC8949
  STD96:
    -: cose
    =: RFC9052
  BCP26:
    -: ianacons
    =: RFC8126

informative:
  RFC9334: rats-arch
  RFC9562: uuidv7
  I-D.ietf-scitt-architecture: scitt-arch

entity:
  SELF: "RFCthis"

--- abstract

This document defines formats for recording and verifying autonomous
agent conversations. It specifies two complementary data structures:
(1) a session trace for chronological conversation replay, capturing
how an agent produced its outputs through entries, tool invocations,
and reasoning steps; and (2) a file attribution record for code-level
provenance tracking, identifying which files were modified, which
line ranges were changed, and which contributors (human, AI, or
mixed) produced each change. Both structures can be independently
wrapped in a COSE_Sign1 {{-cose}} signing envelope for cryptographic
verification, enabling non-repudiation and auditability of agent
activities. The data formats are defined using CDDL {{-cddl}} and
support both JSON {{-json}} and CBOR {{-cbor}} serialization.

--- middle

# Introduction

Autonomous Agents--typically workload instances of agentic artificial
intelligence (AI) based on large language models (LLM)--interact with
other actors by design. The two main types of actors interacting with
autonomous agents are humans and machines (e.g., other autonomous
agents), or a mix of them. In agentic AI systems, machine actors
interact with other machine actors. While the responsible parties
ultimately are humans (e.g., a natural legal entity or an
organization), agents do not only act on behalf of humans; they can
also act on behalf of other agents. These increasingly complex
interactions between multiple actors that can also be triggered by
machines (recursively) increase the need to understand decision making
and the chain of thoughts of autonomous agents, retroactively.

This document defines conversation records representing activities of
autonomous agents such that long-term preservation of the evidentiary
value of these records across chains of custody is possible.

The first goal is to assure that the recording of an agent
conversation (a distinct segment of the interaction with an autonomous
agent) being proffered is the same as the agent conversation that
actually occurred.

The second goal is to provide a general structure of agent
conversations that can represent most common types of agent
conversation frames, is extensible, and allows for future evolution of
agent conversation complexity and corresponding actor interaction.

The third goal is to use existing IETF building blocks to present
believable evidence about how an agent conversation is recorded
utilizing Evidence generation as laid out in the Remote ATtestation
procedureS (RATS) architecture {{-rats-arch}}.

The fourth goal is to use existing IETF building blocks to render
conversation records auditable after the fact and enable
non-repudiation as laid out in the Supply Chain Integrity,
Transparency, and Trust (SCITT) architecture {{-scitt-arch}}.

Most agent conversations today are represented in "human-readable"
text formats. For example, {{-json}} is considered to be
"human-readable" as it can be presented to humans in
human-computer-interfaces (HCI) via off-the-shelf tools, e.g.,
pre-installed text editors that allow such data to be consumed or
modified by humans. The Concise Binary Object Representation (CBOR
{{-cbor}}) is used as the primary representation next to the
established representation that is JSON.

## Conventions and Definitions

{::boilerplate bcp14-tagged}

In this document, CDDL {{-cddl}} is used to describe the data
formats.

The reader is assumed to be familiar with the vocabulary and concepts
defined in {{-rats-arch}} and {{-scitt-arch}}.

The following terms are used in this document:

Recording Agent:
: The software that captures and serializes agent conversations into
  conversation records. Identified by the `cli-name` and
  `cli-version` fields in agent metadata.

Tool Call:
: An invocation of a capability by the agent during a conversation
  session. Represented by the `tool-call-entry` type. Tool calls
  include actions such as editing files, executing commands, or
  searching code.

Session Trace:
: A chronological record of all entries (user inputs, agent
  responses, tool invocations, reasoning steps) that occurred during
  a conversation session.

File Attribution:
: A record of which files were modified during a conversation, which
  line ranges were changed, and which contributors produced each
  change. File attribution can be recorded independently or derived
  from session trace entries.

# Conformance Requirements {#conformance}

## Terminology

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT",
"SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and
"OPTIONAL" in this document are to be interpreted as described in
BCP 14 {{!RFC2119}} {{!RFC8174}} when, and only when, they appear in
all capitals, as shown here.

## Conformance Classes

This specification defines three conformance classes for implementations:

### Producer Conformance

A conforming producer MUST:

1. Generate records that validate against the CDDL schema in
   {{fig-cddl-record}}
2. Include all REQUIRED fields as specified in {{session-trace}} and
   {{file-attribution}}
3. Use RFC 3339 timestamps for all temporal fields
4. Generate unique identifiers for `session-id`, `call-id`, and entry
   identifiers where applicable

A conforming producer SHOULD:

1. Include `reasoning-entry` records when chain-of-thought is available
2. Redact sensitive information from tool call inputs and outputs
   ({{privacy-considerations}})
3. Sign records using COSE_Sign1 when publishing to transparency
   services ({{signing-envelope}})

### Verifier Conformance

A conforming verifier MUST:

1. Validate CDDL schema compliance for records it processes
2. Verify COSE_Sign1 signatures when present
3. Check temporal ordering constraints (tool-result follows tool-call,
   timestamps monotonically increase within a session)
4. Reject records with missing REQUIRED fields

A conforming verifier SHOULD:

1. Verify file attribution derivability from session trace when both
   are present ({{derivation-algorithm}})
2. Check for credential leakage in tool call parameters
   ({{privacy-considerations}})
3. Validate `content_hash` values against actual file content when
   available

### Consumer Conformance

A conforming consumer MUST:

1. Parse records that conform to the CDDL schema
2. Handle all entry types defined in {{session-trace}}
3. Gracefully handle unknown vendor extension fields

A conforming consumer MAY:

1. Ignore fields marked OPTIONAL in the schema
2. Process only a subset of entry types if not relevant to its use case
3. Reject unsigned records or records from untrusted signers

## Integrity Invariants {#integrity-invariants}

A valid session trace MUST satisfy these invariants:

**I1: Temporal Ordering**
For any two entries E1 and E2 in `session.entries[]` where E1 appears
before E2, it MUST be that `E1.timestamp ≤ E2.timestamp`.

**I2: Tool Call Pairing**
For every `tool-result-entry` with `call-id` C, there MUST exist
exactly one `tool-call-entry` with `tool_id` = C appearing earlier in
the entries array.

**I3: Session Bounds**
All entry timestamps MUST fall within [`session-start`, `session-end`]
inclusive. If `session-end` is not present (for incomplete sessions),
this invariant applies only to the `session-start` bound.

**I4: Unique Tool Call IDs**
All `tool_id` values in `tool-call-entry` records within a session
MUST be unique.

**I5: File Attribution Consistency** (when both session and file
attribution are present)
For every file F in `file-attribution.files[]`, there SHOULD exist at
least one `tool-call-entry` in the session trace that references F's
path in its `input` parameters.

These invariants enable verification of trace integrity without
requiring access to the original execution environment.

# Verifiable Agent Record

A verifiable agent record is the top-level container that unifies
two complementary perspectives on agent activity:

- **Session Trace**: captures HOW code was produced -- the full
  chronological conversation including user requests, agent
  reasoning, tool invocations, and results.

- **File Attribution**: captures WHAT code was produced -- which
  files were modified, which line ranges were changed, and by which
  contributors.

Neither perspective subsumes the other. A session trace contains the
full event stream but does not directly enumerate per-file, per-line
attribution. A file attribution record identifies code provenance but
does not capture the reasoning process or conversational context that
led to each modification.

The `verifiable-agent-record` type contains both perspectives as
optional, independently-populated fields, linked by a shared record
identifier. A conforming record MUST include at least one of
`session` or `file-attribution`.

## Common Types

The schema defines several primitive types that are shared across
both session traces and file attribution records.

### Timestamps

Timestamps are represented as either RFC 3339 {{RFC3339}} date-time
strings or numeric epoch milliseconds:

~~~
abstract-timestamp = tstr / number
~~~

Implementations SHOULD use RFC 3339 strings for new records.
Implementations MUST accept epoch milliseconds (number) for
interoperability with existing agent trace formats.

### Identifiers

Session identifiers and entry identifiers are opaque text strings.
Implementations SHOULD use UUID v7 {{RFC9562}} for new session
identifiers.

~~~
session-id = tstr
entry-id = tstr
~~~

# Session Trace {#session-trace}

A session trace captures the full conversation: entries, tool calls,
reasoning, and token usage. It is the primary recording format for
agent activities.

A session trace is either an interactive session (a human-in-the-loop
conversation) or an autonomous session (an agent operating
independently on a task).

## Session Envelope

The session envelope contains fields common to all session types:

- `session-id`: a unique identifier for this session
- `session-start`: timestamp when the session began
- `session-end`: timestamp when the session ended (if known)
- `agent-meta`: metadata about the agent and model
- `environment`: the execution environment (working directory, VCS)
- `entries`: the ordered array of conversation entries

## Agent Metadata

Agent metadata identifies both the AI model used during the
conversation and the recording agent that produced the trace.

The `model-id` and `model-provider` fields identify the model. The
`cli-name` and `cli-version` fields identify the recording agent
software. For example, a session recorded by Claude Code version
2.1.34 using the `claude-opus-4-5-20251101` model would have:

~~~json
{
  "model-id": "claude-opus-4-5-20251101",
  "model-provider": "anthropic",
  "cli-name": "claude-code",
  "cli-version": "2.1.34"
}
~~~

Note: The `cli-name` and `cli-version` fields replace the `tool`
type from earlier versions of this specification, avoiding ambiguity
with the `tool-call-entry` type that represents capability
invocations within the conversation.

## Environment Context

The environment captures the execution context in which the agent
operated, including the working directory, version control state, and
any sandbox configurations.

### Version Control Context

The `vcs-context` type records the repository state at session start:

- `type`: the VCS system ("git", "jj", "hg", "svn")
- `revision`: the commit identifier (SHA for git)
- `branch`: the active branch name
- `repository`: the repository URL or path

## Entry Types {#entry-types}

A session trace contains an ordered array of entries. Each entry
extends a base type with four common fields:

- `type`: a discriminator string identifying the entry type
- `timestamp`: when the entry occurred
- `id`: an optional per-entry unique identifier
- `session-id`: an optional session reference

The following entry types are defined:

### User Entry

A message from the human operator or system prompt to the agent.

### Assistant Entry

A response from the agent, including the model identifier, token
usage, and stop reason.

### Tool Call Entry

An invocation of a capability by the agent. Tool calls are the
primary bridge to file attribution: when an agent calls an editing
tool (such as "Edit", "replace", or "apply_patch"), the tool call
input contains the file path and modification content.

Each tool call has a `call-id` that links it to a corresponding
`tool-result-entry`. Tool calls MAY include a `contributor` field
for multi-agent sessions where different models make different
tool invocations within the same session.

### Tool Result Entry

The result of a tool invocation, linked to the originating tool
call by `call-id`. Includes an output value and optional status
and error indicators.

### Reasoning Entry

Chain-of-thought or internal reasoning content. Reasoning entries
MAY contain plaintext reasoning, encrypted content (for
privacy-preserving traces), or a subject label.

### System Event Entry

Lifecycle events such as session start, session end, context
window compaction, or permission changes.

### Vendor Entry

A catch-all for vendor-specific entry types not covered by the
standard types above. Vendor entries MUST include a
`vendor-extension` field identifying the originating vendor.

# File Attribution {#file-attribution}

File attribution captures which files were modified during a
conversation and provides per-line contributor tracking. This
structure was designed for code provenance: given a file in a
repository, which conversations produced which line ranges, and
was each range written by a human, an AI model, or a mix of both?

## Structure

A file attribution record contains an array of files. Each file has
a relative path (from the repository root) and an array of
conversations that contributed to it. Each conversation contains
an array of ranges representing the line regions that were produced.

## Contributor Types

Contributors are classified as:

- `"human"`: the range was written by a human developer
- `"ai"`: the range was produced by an AI model
- `"mixed"`: the range was produced by collaboration between human
  and AI (e.g., human-written code modified by an AI, or AI-generated
  code modified by a human)
- `"unknown"`: attribution cannot be determined

Each contributor MAY include a `model_id` identifying the specific
model (e.g., `"anthropic/claude-opus-4-5-20251101"`).

## Relationship to Session Trace

File attribution can be PARTIALLY derived from session trace entries
by analyzing tool calls that modify files. The derivation algorithm
({{derivation-algorithm}}) describes this process.

However, two fields CANNOT be derived from session trace entries
alone:

- `content_hash`: requires access to the final file state after all
  edits have been applied, which is not captured in the session
  trace.
- `conversation.url`: an external reference to the conversation
  source, which must be provided by the recording system.

Implementations MAY generate file attribution records by any means,
including direct file system instrumentation, VCS analysis, or the
derivation algorithm.

# Signing Envelope {#signing-envelope}

Verifiable agent records can be wrapped in a COSE_Sign1 {{-cose}}
signing envelope to provide cryptographic verification. Signing is
INDEPENDENT of schema compliance: a record can be signed regardless
of whether it conforms to the session trace or file attribution
schemas defined in this document.

## COSE_Sign1 Structure

The signing envelope uses COSE Single Signer Data Object
(COSE_Sign1) as defined in {{-cose}}. The structure is:

~~~
COSE_Sign1 = [
    protected: bstr,      ; Protected header (algorithm, content-type)
    unprotected: {},       ; Unprotected header (trace metadata)
    payload: bstr / null,  ; Serialized record (or detached)
    signature: bstr        ; Cryptographic signature
]
~~~

The `protected` header MUST include the signature algorithm
identifier. The `payload` contains the serialized record bytes;
when JSON is the payload format, the UTF-8 encoded JSON bytes are
used. A `null` payload indicates a detached signature where the
payload is conveyed separately.

## Trace Metadata

The unprotected header MAY include trace metadata for efficient
routing and filtering without payload deserialization:

- `session-id`: the session identifier from the enclosed record
- `agent-vendor`: the vendor that produced the trace
- `trace-format`: a registered format identifier
- `timestamp-start` and `timestamp-end`: the time range of the
  session
- `content-hash`: a hash digest of the payload bytes

## Trace Format Registry

Trace format identifiers allow receivers to determine the payload
format without deserializing the content. The following initial
values are defined:

| Identifier | Description |
|:-----------|:------------|
| `ietf-vac-v2.0` | This specification's format |
| `claude-jsonl` | Claude Code native JSONL |
| `gemini-json` | Gemini CLI single-JSON |
| `codex-jsonl` | Codex CLI JSONL |
| `opencode-json` | OpenCode concatenated JSON |
{: #tab-formats title="Initial Trace Format Identifiers"}

This list is extensible; implementations MAY use any string value
for vendor-specific formats.

## Verification Goals

The signing envelope satisfies two of the four goals stated in
{{introduction}}:

- **Goal 3 (RATS Evidence)**: A signed conversation record
  constitutes Evidence in the RATS architecture {{-rats-arch}}. The
  signing key identifies the Attester (the recording agent), and the
  signature provides integrity protection over the conversation
  content.

- **Goal 4 (SCITT Auditability)**: A signed conversation record can
  be submitted to a SCITT Transparency Service {{-scitt-arch}} as a
  Signed Statement, enabling public auditability and non-repudiation
  of agent activities.

# Vendor Extensions {#vendor-extensions}

The vendor extension mechanism allows implementations to include
format-specific fields without modifying the base schema.

## Structure

A vendor extension wraps opaque data with provenance information:

- `vendor`: a required string identifying the extension source
- `version`: an optional schema version for this vendor's extensions
- `data`: the vendor-specific payload

## Key Types

Extension data supports both string keys (for JSON compatibility)
and integer keys (for compact CBOR encoding):

~~~
extension-data = { * extension-key => any }
extension-key = tstr / int
~~~

JSON implementations MUST use string keys exclusively. CBOR
implementations MAY use integer keys for compact encoding when
both producer and consumer agree on the integer key assignments.

## Extension Points

Vendor extensions appear at multiple levels in the schema:

- Session envelope level (session-wide metadata)
- Agent metadata level (model-specific extensions)
- Environment level (infrastructure metadata)
- Entry level (per-entry vendor data)
- Token usage level (cost and billing extensions)

# Security Considerations

## Recording Integrity

The session trace format records agent activities as they occur.
Implementations MUST NOT allow retroactive modification of entries
after they have been recorded. When entries are appended to a
session trace during an active session, each entry SHOULD include
a timestamp to support ordering verification.

## Credential Exclusion

Session traces MAY contain tool call inputs and outputs that
include sensitive information such as API keys, authentication
tokens, or personal data. Implementations MUST provide mechanisms
to redact sensitive content before recording. The `reasoning-entry`
type supports an `encrypted` field for privacy-preserving storage
of chain-of-thought content.

## Signing Key Management

The COSE_Sign1 signing envelope requires careful key management.
The signing key identifies the recording agent (Attester in RATS
terminology). Compromise of the signing key would allow creation
of forged conversation records. Implementations SHOULD use
hardware-backed key storage where available.

## Derivation Algorithm Limitations

The file attribution derivation algorithm ({{derivation-algorithm}})
is INFORMATIVE and inherently incomplete. It cannot derive
`content_hash` values without access to the final file state, and
it cannot attribute file modifications made outside the agent
session (e.g., concurrent human edits in a text editor). Security
decisions MUST NOT rely solely on derived file attribution; instead,
independently-recorded file attribution records SHOULD be used when
high-assurance provenance is required.

## Multi-Agent Trust

In multi-agent sessions where sub-agents operate on behalf of a
parent agent, the `contributor` field on `tool-call-entry` enables
per-action attribution. However, the trust relationship between
agents is out of scope for this document. Implementations that
process multi-agent traces SHOULD verify the identity chain from
sub-agent to parent agent to responsible human.

# Privacy Considerations

## Personal Information in Traces

Agent sessions often involve user-supplied prompts that may contain
personal information, proprietary source code, confidential business
logic, or sensitive system configurations. Organizations publishing
signed conversation records MUST establish policies for what constitutes
publishable content.

Recommended redaction targets include:

- API keys, passwords, and authentication tokens
- Personal names, email addresses, and contact information
- IP addresses and internal network configurations
- Proprietary algorithms and trade secrets
- Confidential file paths revealing organizational structure

## Reasoning Entry Privacy

The `reasoning-entry` type includes an optional `encrypted` field to
support privacy-preserving publication of chain-of-thought traces.
When set to true, implementations SHOULD encrypt the reasoning content
before publication and provide the decryption key only to authorized
auditors. This allows compliance verification (proving reasoning
occurred) without revealing proprietary reasoning patterns.

## Differential Privacy for Benchmarks

When aggregating conversation records into public benchmarks (e.g.,
"1000 CVE-fixing sessions"), publishers SHOULD apply differential
privacy techniques to prevent inference of individual session details
from aggregate statistics. Specific concerns include:

- Model fingerprinting: Inference of which model was used based on
  token usage patterns
- Prompt reconstruction: Reverse-engineering user prompts from tool
  call sequences
- Capability disclosure: Revealing unreleased model features through
  trace analysis

## Right to Deletion

Organizations providing agent services MUST respect user deletion
requests for conversation records. However, once a signed record is
published to a transparency log (e.g., SCITT feed), cryptographic
immutability prevents deletion. Implementations SHOULD document the
permanence of signed publication and obtain explicit consent before
submitting records to transparency services.

# IANA Considerations

## Trace Format Registry

IANA is requested to create a new registry titled "Verifiable Agent
Conversation Trace Formats" with the following registration policy:

- Registration Policy: Specification Required {{-ianacons}}
- Reference: {{SELF}}

Initial entries are listed in {{tab-formats}}.

## Media Type Registrations

IANA is requested to register the following media types:

### application/verifiable-agent-record+json

- Type name: application
- Subtype name: verifiable-agent-record+json
- Required parameters: None
- Optional parameters: None
- Encoding considerations: binary (UTF-8 JSON)
- Security considerations: See {{security-considerations}}
- Interoperability considerations: See {{interoperability}}
- Published specification: {{SELF}}
- Applications that use this media type: AI agent recorders, SCITT
  transparency services, RATS verifiers
- Fragment identifier considerations: JSON Pointer (RFC 6901)
- Additional information: None
- Person & email address to contact: [WG chairs]
- Intended usage: COMMON
- Restrictions on usage: None
- Author: See {{authors}}
- Change controller: IETF

### application/verifiable-agent-record+cbor

- Type name: application
- Subtype name: verifiable-agent-record+cbor
- Required parameters: None
- Optional parameters: None
- Encoding considerations: binary
- Security considerations: See {{security-considerations}}
- Interoperability considerations: See {{interoperability}}
- Published specification: {{SELF}}
- Applications that use this media type: AI agent recorders, SCITT
  transparency services, RATS verifiers, SUIT manifest dependencies
- Fragment identifier considerations: CBOR Pointer (RFC 9535)
- Additional information: None
- Person & email address to contact: [WG chairs]
- Intended usage: COMMON
- Restrictions on usage: None
- Author: See {{authors}}
- Change controller: IETF

--- back

# File Attribution Derivation Algorithm {#derivation-algorithm}

This appendix describes an informative algorithm for deriving a
file attribution record from session trace entries. This algorithm
is NOT NORMATIVE; implementations MAY generate file attribution
records by any means.

## Algorithm Steps

1. Initialize an empty file map: `{ path -> [conversation] }`

2. Walk `session-trace.entries[]` in chronological order.

3. For each `tool-call-entry` where `name` is one of the recognized
   file-modifying tools ("Edit", "Write", "replace", "apply_patch",
   "edit_file", "write_file"):

   a. Extract `file_path` from `input` (the key name varies by
      recording agent implementation).

   b. Normalize to a relative path by stripping the working
      directory prefix from `environment.working-dir`.

   c. Create or update the file entry in the file map.

4. For each corresponding `tool-result-entry` (linked by `call-id`):

   a. If `status` is "success", the modification is confirmed.

   b. If vendor-specific metadata is available (e.g., OpenCode's
      `metadata.files[]`), extract the unified diff, line numbers,
      and addition/deletion counts.

5. Determine the contributor:

   a. `contributor.type` = "ai" for agent-produced modifications.

   b. `contributor.model_id` = the `model-id` from `agent-meta` or
      the `model-id` from the preceding `assistant-entry`.

6. For multi-agent sessions, use the per-entry `model-id` (which
   may differ from the session-level `agent-meta.model-id`).

## Non-Derivable Fields

The following fields CANNOT be derived from session trace entries
alone and require external data sources:

- `range.content_hash`: Requires reading the final file state after
  ALL edits in the session have been applied. The session trace
  records edit operations, not resulting file states.

- `conversation.url`: An external reference to the conversation
  source (e.g., a sharing URL). Must be provided by the recording
  system.

- `range.start_line` / `range.end_line` (for some recording
  agents): Recording agents that use string-matching edit semantics
  (old_string/new_string replacement) do not include line numbers
  in the tool call input. Deriving line numbers requires matching
  the old_string against the file content at the time of the edit,
  which requires maintaining a running model of the file state.

# Empirical Basis {#empirical-basis}

<!-- See: PR #2 agent-conversation.cddl for the schema derived from this dataset -->
<!-- See: PR #4 examples/DATASET_MANIFEST.md for complete dataset inventory -->
<!-- See: PR #4 examples/traces/ for representative trace samples -->
<!-- See: PR #4 examples/reasoning-artifacts/ for full derivation chain (RLM→Agent0→Quint→Council) -->

The data formats defined in this document are derived from empirical
analysis of 4 agent implementations across 221 coding sessions that
addressed 23 distinct software vulnerabilities.

## Agent Implementations Analyzed

| Agent | Provider | Trace Format | Key Characteristics |
|:------|:---------|:-------------|:--------------------|
| Claude Code | Anthropic | JSONL | Per-entry timestamps, tree-structured messages, Edit tool with old/new string semantics |
| Gemini CLI | Google | Single JSON | Array-based messages, replace tool, instruction field |
| Codex CLI | OpenAI | JSONL | Response items, apply_patch with custom diff format, shell fallback |
| OpenCode | Community | Concatenated JSON | Rich file metadata (diffs, before/after content, line counts), multi-provider support |
{: #tab-agents title="Agent Implementations Analyzed"}

## Coverage and Limitations

- Task bias: All sessions involved vulnerability remediation (CVE
  fixing). General-purpose coding tasks, documentation, testing,
  and other activities are not represented.
- Sample density: Approximately 2.4 sessions per agent-format per
  vulnerability.
- Temporal snapshot: Agent versions from February 2026. Agent trace
  formats may evolve.
- Agent coverage: 4 of 9+ known AI coding agents are represented.
  Notable omissions include Cursor, Windsurf, and Devin.

# Test Vectors {#test-vectors}

<!-- See: PR #2 agent-conversation.cddl for schema validation -->
<!-- See: PR #4 examples/traces/ for real-world agent trace samples (Claude, Gemini, Codex, OpenCode) -->
<!-- See: Section: Empirical Basis for dataset context -->

This appendix provides concrete examples of valid verifiable agent records.

## Minimal Session Trace

A minimal valid record containing a single user-assistant exchange:

~~~ json
{
  "version": "0.1.0",
  "id": "trace-001",
  "created": "2026-02-09T10:00:00Z",
  "session": {
    "start_time": "2026-02-09T10:00:00Z",
    "end_time": "2026-02-09T10:01:30Z",
    "entries": [
      {
        "type": "user",
        "timestamp": "2026-02-09T10:00:00Z",
        "content": "Fix the authentication bug in login.py"
      },
      {
        "type": "assistant",
        "timestamp": "2026-02-09T10:01:00Z",
        "content": "I'll add input validation to prevent SQL injection."
      },
      {
        "type": "tool-call",
        "timestamp": "2026-02-09T10:01:15Z",
        "tool_name": "edit_file",
        "tool_id": "call-001",
        "parameters": {
          "path": "login.py",
          "old_string": "query = f\"SELECT * FROM users WHERE name='{username}'\"",
          "new_string": "query = \"SELECT * FROM users WHERE name=?\" with (username,)"
        }
      },
      {
        "type": "tool-result",
        "timestamp": "2026-02-09T10:01:25Z",
        "tool_call_id": "call-001",
        "status": "success"
      }
    ]
  }
}
~~~
{: #fig-minimal-trace artwork-align="left" title="Minimal Session Trace"}

## Session Trace with File Attribution

A record combining conversation provenance with code-level attribution:

~~~ json
{
  "version": "0.1.0",
  "id": "trace-002",
  "created": "2026-02-09T11:00:00Z",
  "session": {
    "start_time": "2026-02-09T11:00:00Z",
    "end_time": "2026-02-09T11:05:00Z",
    "entries": [
      {
        "type": "user",
        "timestamp": "2026-02-09T11:00:00Z",
        "content": "Add rate limiting to the API"
      },
      {
        "type": "tool-call",
        "timestamp": "2026-02-09T11:02:00Z",
        "tool_name": "write_file",
        "tool_id": "call-002",
        "parameters": {
          "path": "api/middleware.py",
          "content": "from flask_limiter import Limiter..."
        }
      }
    ]
  },
  "file-attribution": {
    "files": [
      {
        "path": "api/middleware.py",
        "content_hash": "sha256:abc123...",
        "operations": [
          {
            "type": "create",
            "line_range": [1, 45],
            "contributors": [
              {
                "type": "ai-agent",
                "name": "Claude Code",
                "version": "2.0.76"
              }
            ]
          }
        ]
      }
    ]
  },
  "vcs": {
    "repository_url": "https://github.com/acme/api",
    "commit_hash": "def456",
    "branch": "feat/rate-limiting"
  }
}
~~~
{: #fig-combined-trace artwork-align="left" title="Session with File Attribution"}

## Signed Record with Vendor Extension

A COSE-signed record with custom metadata:

~~~ cbor-diag
/ COSE_Sign1 structure (RFC 9052) /
18([
  / protected headers /
  << {
    1: -7,  / alg: ES256 /
    3: "application/verifiable-agent-record+cbor"
  } >>,
  / unprotected headers /
  {},
  / payload (verifiable-agent-record) /
  << {
    "version": "0.1.0",
    "id": "trace-003",
    "created": 1707473400,
    "session": {
      "start_time": 1707473400,
      "end_time": 1707473700,
      "entries": [...]
    },
    "metadata": {
      "vendor": "acme-ai",
      "version": "1.0",
      "data": {
        "cost_usd": 0.042,
        "model": "gpt-4-turbo",
        "tokens": 1250
      }
    }
  } >>,
  / signature /
  h'3045022100...0220...'
])
~~~
{: #fig-signed-trace artwork-align="left" title="Signed Record with Vendor Data"}

# Implementation Considerations {#implementation-considerations}

<!-- See: PR #2 agent-conversation.cddl for normative schema definition -->
<!-- See: PR #4 docs/cddl-extraction-methodology.md for schema derivation process -->
<!-- See: PR #4 docs/agent-type-mapping-table.md for vendor format conversion guidance -->
<!-- See: Section: Conformance Requirements for Producer/Verifier/Consumer classes -->

This section provides guidance for building conforming producers,
verifiers, and consumers.

## Producer Implementation

### Streaming vs Batch Recording

Producers MAY record session entries in streaming mode (appending to
the trace as events occur) or batch mode (generating the complete
trace after session completion).

**Streaming advantages:**
- Lower memory footprint for long sessions
- Real-time monitoring and debugging
- Partial trace availability if agent crashes

**Batch advantages:**
- Simpler implementation (no concurrent append coordination)
- Easier to ensure invariant satisfaction (full session state available)
- Atomic signing (sign complete trace, not incremental updates)

For sessions expected to exceed 1000 entries or 1 hour duration,
streaming mode is RECOMMENDED.

### Timestamp Generation

Producers MUST generate timestamps that satisfy the temporal ordering
invariant (I1). Two approaches are common:

**System Clock Approach:**
Query system time for each entry. Risk: clock skew during session can
violate monotonicity. Mitigation: Detect backward clock movement and
either reject the event or use the previous timestamp + 1ms.

**Logical Clock Approach:**
Initialize a counter at session start, increment for each entry, and
convert to timestamp using session-start as epoch. Guarantees
monotonicity but loses wall-clock correspondence.

**Hybrid Approach (RECOMMENDED):**
Use system clock but enforce monotonicity: `timestamp[i] = max(
system_time(), timestamp[i-1] + 1ms)`. Preserves wall-clock fidelity
while guaranteeing I1.

### Tool Call ID Generation

Tool call IDs MUST be unique within a session (I4). Recommended
strategies:

- **UUID v7** (RFC 9562): Embeds timestamp, sortable, 128-bit
  collision resistance
- **Sequential integers**: Simple, compact, requires session-scoped
  counter
- **Prefixed counters**: `call-001`, `call-002`, human-readable

Producers SHOULD NOT use UUIDs shorter than 128 bits (e.g., UUID v4
truncated to 64 bits) as collision risk becomes non-negligible for
sessions with 10,000+ tool calls.

## Verifier Implementation

### CDDL Validation

Verifiers MUST validate records against the CDDL schema. Available
implementations:

- **cddl-rust** (Rust): Full RFC 8610 support, streaming validation
- **cddl-js** (JavaScript/TypeScript): Subset support, browser-compatible
- **pycddl** (Python): Full support, good error messages

Verifiers SHOULD cache compiled CDDL schemas to avoid re-parsing on
every validation.

### Signature Verification Pipeline

For COSE_Sign1-wrapped records, verifiers SHOULD implement a
multi-stage pipeline:

1. **Structural validation**: Verify COSE_Sign1 envelope structure
   (4-element array)
2. **Algorithm support check**: Verify the `alg` parameter is supported
   (e.g., ES256, ES384, EdDSA)
3. **Key retrieval**: Fetch public key from key identifier or
   certificate chain
4. **Signature verification**: Cryptographically verify the signature
   over the protected headers and payload
5. **Payload validation**: Decode payload and validate against CDDL
6. **Invariant checking**: Verify integrity invariants I1-I5

Separating stages enables clearer error reporting ("signature invalid"
vs "payload schema mismatch").

### Partial Trace Handling

Verifiers MAY accept traces where `session-end` is absent (incomplete
sessions). In this case:

- Invariant I3 (Session Bounds) applies only to `session-start` lower
  bound
- Tool Call Pairing (I2) may have unpaired `tool-call-entry` records
  if the session crashed before results arrived

Verifiers SHOULD document whether they accept partial traces and under
what circumstances.

## Consumer Implementation

### Entry Type Dispatching

Consumers MUST handle all entry types but MAY ignore entry types not
relevant to their use case. A common pattern is a dispatch table:

~~~python
def process_entry(entry):
    handlers = {
        "user": handle_user_entry,
        "assistant": handle_assistant_entry,
        "tool-call": handle_tool_call,
        "tool-result": handle_tool_result,
        "reasoning": handle_reasoning,
        "system-event": handle_system_event,
    }
    handler = handlers.get(entry["type"], handle_unknown)
    handler(entry)
~~~

The `handle_unknown` fallback enables forward compatibility: future
entry types are silently ignored rather than causing parse failures.

### Vendor Extension Handling

Consumers MUST tolerate unknown vendor extension fields. When
deserializing records, consumers SHOULD preserve unknown fields to
enable round-trip serialization (read, modify, write without data loss).

**JSON Example (JavaScript):**

~~~javascript
// Parse with full object preservation
const record = JSON.parse(traceData);

// Access known fields
const sessionId = record.session["session-id"];

// Unknown fields in record.metadata.data are preserved
// even if not explicitly accessed

// Re-serialize without data loss
const updated = JSON.stringify(record);
~~~

**CBOR Example (Rust):**

~~~rust
use ciborium::Value;

// Parse as dynamic CBOR value
let record: Value = ciborium::from_reader(reader)?;

// Extract known fields with pattern matching
if let Value::Map(map) = record {
    // Unknown map entries are preserved in Value::Map
}
~~~

### Performance Considerations

For traces with 10,000+ entries:

- **Streaming parsers**: Use SAX-style or streaming JSON/CBOR parsers
  to avoid loading the entire trace into memory
- **Entry indexing**: Build an index of entry timestamps or tool-call
  IDs for fast lookup
- **Lazy loading**: Load `file-attribution` separately from
  `session-trace` if only one is needed

# Interoperability Considerations {#interoperability}

This section describes how verifiable agent records integrate with
existing IETF attestation and supply chain standards.

## Relationship to RATS Architecture

The Remote ATtestation procedureS (RATS) architecture {{?RFC9334}}
defines evidence, attestation results, and verifier roles. Verifiable
agent records serve as **Evidence** in RATS terminology:

- Attester: The AI agent or recording infrastructure
- Verifier: Any party validating the signature and trace integrity
- Relying Party: Downstream consumers (auditors, compliance tools)

The COSE_Sign1 envelope provides the cryptographic Evidence binding.
A RATS Verifier could check:

1. Signature validity (keys, freshness)
2. Trace completeness (all tool calls have results)
3. File attribution consistency (hashes match operations)

## Relationship to SCITT Architecture

The Supply Chain Integrity, Transparency and Trust (SCITT) architecture
defines transparent statements about supply chain artifacts. A
verifiable agent record can be registered as a SCITT Statement:

- Statement: The verifiable-agent-record payload
- Envelope: COSE_Sign1 wrapping
- Feed: A collection of related agent sessions (e.g., all traces for a
  repository)

The `vcs.commit_hash` field provides the linkage to supply chain
artifacts (code commits). SCITT Transparency Services could enable:

1. Discoverability: "Find all AI contributions to commit abc123"
2. Auditability: "Verify no unsigned AI changes in production"
3. Accountability: "Identify which agent version introduced a bug"

## Relationship to SUIT Manifests

Software Updates for Internet of Things (SUIT) {{?RFC9124}} defines
manifests for firmware updates. While agent records focus on
*development-time* provenance, they complement SUIT's *deployment-time*
verification:

- SUIT manifest: "This firmware binary is authentic"
- Agent record: "This code change was made by agent X with oversight Y"

Organizations could require BOTH:

1. SUIT manifest signature for the deployed artifact
2. Agent record coverage for any AI-contributed code in the artifact

This creates a chain of custody from development through deployment.

## Media Type Registration

To enable interoperability, this specification defines two media types:

- `application/verifiable-agent-record+json`: JSON-encoded records
- `application/verifiable-agent-record+cbor`: CBOR-encoded records

These media types can be used in:

- HTTP Content-Type headers when transmitting records
- SCITT statement payload type identifiers
- SUIT manifest dependency annotations

# Security Analysis {#security-analysis}

This appendix provides a comprehensive threat model and security
analysis for verifiable agent conversation systems.

## Threat Model

### Adversary Capabilities

We consider three adversary classes:

**A1: Passive Observer**
- Capabilities: Read published trace records, analyze patterns
- Goal: Infer proprietary information (prompts, model capabilities, user behavior)
- Motivation: Competitive intelligence, social engineering

**A2: Active Attacker**
- Capabilities: Modify traces, forge signatures, inject malicious entries
- Goal: Frame AI agents for unauthorized actions, hide malicious activity
- Motivation: Reputation damage, legal liability evasion

**A3: Insider Threat**
- Capabilities: Access to signing keys, recording infrastructure, raw traces
- Goal: Fabricate complete traces, selectively omit entries, backdate records
- Motivation: Cover up mistakes, plant false evidence

### Trust Boundaries

**TB1: Agent → Recording Infrastructure**
The agent runtime sends entries to the recording system. If the agent is
compromised, it may emit false entries or omit entries.

**TB2: Recording Infrastructure → Transparency Service**
The recording system signs and publishes records. If compromised, it may
forge signatures or modify entries before signing.

**TB3: Transparency Service → Verifier**
Verifiers fetch records from transparency logs. If the log is compromised,
it may serve different records to different verifiers (equivocation).

**TB4: Verifier → Relying Party**
Relying parties make decisions based on verifier output. If the verifier
is compromised, it may provide false attestations.

## Attack Vectors

### AV1: Trace Fabrication

**Attack**: Adversary generates a fake trace showing an agent performed
beneficial work it never actually did.

**Mitigation**:
1. COSE_Sign1 signatures bind traces to recording agent identity
2. File attribution `content_hash` enables independent verification
   against actual file state
3. VCS commit hashes provide tamper-evident history
4. Transparency logs prevent post-facto trace generation (timestamps are
   publicly auditable)

**Residual Risk**: If signing key is compromised, fabrication succeeds.
Mitigation requires hardware-backed key storage (TPM, HSM).

### AV2: Selective Entry Omission

**Attack**: Adversary removes embarrassing entries (e.g., failed tool
calls, reasoning errors) from a trace before signing.

**Mitigation**:
1. Integrity invariant I2 (Tool Call Pairing) detects missing
   tool-result entries
2. Integrity invariant I3 (Session Bounds) detects timestamp gaps
3. File attribution derivation algorithm (Appendix A) may detect
   unexplained file modifications

**Residual Risk**: Omission of complete tool-call/tool-result pairs is
undetectable without external ground truth.

### AV3: Timestamp Manipulation

**Attack**: Adversary backdates a trace to claim work was completed
earlier than reality (e.g., for patent priority).

**Mitigation**:
1. Transparency logs use receipt-time timestamps independent of trace
   timestamps
2. SCITT feed anchors provide cryptographic proof of publication time
3. VCS commit timestamps provide corroborating evidence

**Residual Risk**: If transparency log and VCS are both compromised,
backdating succeeds.

### AV4: Signature Stripping

**Attack**: Adversary removes COSE_Sign1 envelope to evade signature
verification.

**Mitigation**:
1. Verifiers MUST reject unsigned records when signature is expected
   ({{conformance}})
2. Transparency logs SHOULD require signatures for submission
3. Policy: Require signed records for high-assurance use cases

**Residual Risk**: If policy is not enforced, unsigned records may be
accepted.

### AV5: Key Compromise → Retroactive Forgery

**Attack**: Adversary compromises signing key, then fabricates historical
traces with backdated timestamps.

**Mitigation**:
1. Transparency logs anchor records at publication time, preventing
   retroactive insertion
2. Key rotation with overlap periods: New key signs "key rotation"
   system-event entry
3. Certificate Transparency-style gossip protocols detect equivocation

**Residual Risk**: If transparency log is also compromised, retroactive
forgery succeeds.

### AV6: Credential Leakage via Trace Publication

**Attack**: API keys or tokens embedded in tool-call inputs are
inadvertently published in signed traces.

**Mitigation**:
1. Privacy Considerations ({{privacy-considerations}}) mandate credential
   redaction
2. Producers SHOULD use allow-list filtering: Only specific tool-call
   parameters are recorded
3. Post-hoc scanning: Automated tools scan traces for credential patterns
   before publication

**Residual Risk**: Novel credential formats or obfuscated secrets may
evade filters.

### AV7: Differential Privacy Violation

**Attack**: Adversary infers individual session details from aggregate
benchmark statistics.

**Mitigation**:
1. Privacy Considerations ({{privacy-considerations}}) recommend
   differential privacy techniques
2. Aggregation thresholds: Publish statistics only for N ≥ 50 sessions
3. Noise injection: Add calibrated random noise to summary statistics

**Residual Risk**: Sophisticated attacks (e.g., membership inference) may
succeed with large-N datasets.

### AV8: Reasoning Entry Privacy Leakage

**Attack**: Adversary extracts proprietary reasoning patterns from
published reasoning-entry records.

**Mitigation**:
1. Reasoning-entry `encrypted` field enables selective encryption
2. Publishers can omit reasoning-entry entirely (OPTIONAL in schema)
3. Differential privacy on reasoning content before publication

**Residual Risk**: Even encrypted reasoning metadata (entry count,
timestamps) may leak patterns.

## Security Properties

Assuming correct implementation and uncompromised keys/infrastructure,
this specification provides:

**SP1: Integrity** - Traces cannot be modified without detection
(COSE_Sign1 + integrity invariants)

**SP2: Authenticity** - Trace origin is verifiable (COSE_Sign1 signature
+ key binding)

**SP3: Non-repudiation** - Signed traces provide evidence of agent
actions (cryptographic proof)

**SP4: Transparency** - Public logs enable third-party auditing
(SCITT/transparency log integration)

**NOT PROVIDED:**

- **Confidentiality**: Traces are public by default (encryption is
  optional per-field)
- **Anonymity**: Signatures bind traces to agent identity (unavoidable
  for accountability)
- **Completeness**: No proof that all entries are included (selective
  omission is undetectable)

# Acknowledgements
{:numbered="false"}

This work was informed by analysis of agent trace formats produced by
Claude Code (Anthropic), Gemini CLI (Google), Codex CLI (OpenAI),
and OpenCode. The authors thank the developers of these tools for
producing structured trace outputs that enabled empirical analysis.

The authors also acknowledge the RATS, SCITT, and SUIT working groups
for establishing the attestation and supply chain foundations that this
work builds upon.

# CDDL Schema
{:numbered="false"}

~~~ cddl
{::include agent-conversation.cddl}
~~~
{: #fig-cddl-record artwork-align="left"
   title="CDDL definition of Verifiable Agent Conversations"}
