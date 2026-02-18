#!/usr/bin/env python3
"""
Validate agent session traces against the CDDL schema.

This script reads raw session files from each agent (Claude Code, Gemini CLI,
Codex CLI, OpenCode, Cursor) and checks whether their data can be mapped into
the `verifiable-agent-record` schema defined in agent-conversation.cddl.

Each agent uses a different native format. The mapping per agent is:

  CDDL field     | Claude           | Gemini      | Codex                  | OpenCode        | Cursor
  type: "user"   | .message.role    | .type        | .payload.role          | .role / messageID→role | .role
  timestamp      | .timestamp       | .timestamp   | .timestamp             | .time.created   | (none)
  content        | .message.content | .content     | .payload.content[].text| .text           | .message.content[].text
  id             | .uuid            | .id          | (positional)           | .id             | (none)
  session-id     | .sessionId       | .sessionId   | .payload.id            | .sessionID      | (none)
  model-id       | .message.model   | .model       | .payload.model         | .modelID        | (none)
  provider       | (inferred)       | (inferred)   | .payload.model_provider| .providerID     | (none)

Fields are only included when present in the native format. The CDDL schema
marks timestamp, content, and call-id as optional to accommodate agents that
don't record them (Cursor lacks timestamps entirely; OpenCode message-level
objects lack inline content).

Known accepted behaviors:

  Codex duplicate entries (~13% inflation):
    Both response_item and event_msg fire for the same reasoning step,
    user message, and assistant message. The response_item version is the
    canonical record (includes encrypted_content for reasoning); the
    event_msg version is a streaming notification with the same content.
    Both are emitted as separate entries. Verified: 71/74 overlapping
    timestamps have identical content across both sources.

  Codex function_call arguments are JSON strings:
    The OpenAI Responses API stores function arguments as a JSON-encoded
    string (e.g., '{"cmd":"rg ..."}'), not as a parsed object. This is
    passed through as-is. The CDDL schema allows `input: any`, so
    strings are valid. Other agents (Claude, OpenCode) pass dicts.

  Empty content on reasoning entries (Codex, OpenCode):
    OpenAI's encrypted reasoning model provides an optional plaintext
    summary. When no summary is available (gpt-5.2-codex and o3 models
    never provide one), the content field is an empty string. The actual
    reasoning is in the `encrypted` field (Fernet-encrypted). This is
    faithful to the source data.

  OpenCode message-level entries without content:
    OpenCode stores message-level objects (role="user"/"assistant") as
    envelope markers with no inline text. The actual content follows in
    separate child objects (type="text", type="tool", type="reasoning").
    The message-level entry is emitted without a content field.

  Cursor zero metadata:
    Cursor exports contain no session ID, no timestamps, no model
    identification, no entry IDs. This is a known limitation of
    Cursor's export format. Session IDs are generated for the record
    envelope. Model/provider are set to "unknown".

Usage:
  python3 scripts/validate-sessions.py [OPTIONS]

Options:
  --schema PATH        Path to CDDL schema file (default: agent-conversation.cddl
                       relative to repo root)
  --sessions-dir PATH  Directory containing session files (default: examples/sessions/
                       relative to repo root)
  --samples N          Max sessions to validate per agent (default: all)
  --verbose            Print full CDDL error output on failures

Requires: cddl gem (available via `nix develop` or `gem install cddl`)
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "agent-conversation.cddl"
DEFAULT_SESSIONS = REPO_ROOT / "examples" / "sessions"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _content_to_str(content):
    """Flatten content field (string, list of parts, etc.) to a string.
    Handles arbitrarily nested structures (e.g. Claude tool_result content
    where 'content' is itself a list of dicts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                inner = c.get("text", c.get("content", ""))
                parts.append(_content_to_str(inner))
            else:
                parts.append(str(c))
        return "\n".join(parts)
    if isinstance(content, dict):
        return _content_to_str(content.get("text", content.get("content", str(content))))
    return str(content)


def _make_entry(type_val, **kwargs):
    """Build an entry dict, only including keys with non-None values."""
    entry = {"type": type_val}
    for k, v in kwargs.items():
        if v is not None:
            entry[k] = v
    return entry


def _infer_provider(model_id):
    """Infer provider from model ID prefix."""
    if not model_id or model_id == "unknown":
        return "unknown"
    if model_id.startswith("claude"):
        return "anthropic"
    if model_id.startswith("gemini"):
        return "google"
    if model_id.startswith("gpt") or model_id.startswith("o3") or model_id.startswith("o4"):
        return "openai"
    return "unknown"


# ---------------------------------------------------------------------------
# Parsers: read native format, yield (entries, metadata) with minimal mapping
# ---------------------------------------------------------------------------


def parse_claude(path):
    """Claude Code: JSONL, one event per line.

    Each JSONL line maps to ONE entry. Assistant and user messages that contain
    multiple content blocks (tool_use, tool_result, thinking) produce a single
    parent entry with typed children.

    Content is passed through as-is (string or array of blocks).
    Model extracted from: message.model on assistant lines.
    Provider inferred from: claude- prefix on model ID.
    """
    with open(path) as f:
        lines = [json.loads(line) for line in f if line.strip()]

    meta = {
        "session_id": None,
        "model_id": "unknown",
        "provider": None,
        "cli": "claude-code",
        "cli_version": None,
        "start": None,
        "cwd": None,
        "branch": None,
        "models": set(),
    }
    entries = []

    for line in lines:
        ts = line.get("timestamp")
        if not meta["start"] and ts:
            meta["start"] = ts
        if line.get("sessionId"):
            meta["session_id"] = line["sessionId"]
        if line.get("version"):
            meta["cli_version"] = line["version"]
        if line.get("cwd"):
            meta["cwd"] = line["cwd"]
        if line.get("gitBranch"):
            meta["branch"] = line["gitBranch"]

        line_id = line.get("uuid")

        if line.get("type") == "queue-operation":
            entries.append(_make_entry("system-event", timestamp=ts, id=line_id, **{"event-type": "queue-operation"}))
            continue

        msg = line.get("message", {})
        role = msg.get("role")
        if not role:
            continue

        model = msg.get("model")
        if model:
            meta["model_id"] = model
            meta["models"].add(model)

        content = msg.get("content", "")

        if role == "user":
            entry = _make_entry("user", timestamp=ts, id=line_id, content=content)
            # Extract typed children from content blocks
            if isinstance(content, list):
                children = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "tool_result":
                        children.append(
                            _make_entry(
                                "tool-result",
                                **{"call-id": part.get("tool_use_id")},
                                output=part.get("content", ""),
                                status="error" if part.get("is_error") else "success",
                            )
                        )
                if children:
                    entry["children"] = children
            entries.append(entry)

        elif role == "assistant":
            entry = _make_entry("assistant", timestamp=ts, id=line_id, content=content)
            # Extract typed children from content blocks
            if isinstance(content, list):
                children = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "tool_use":
                        children.append(
                            _make_entry(
                                "tool-call",
                                name=part.get("name", "unknown"),
                                input=part.get("input", {}),
                                **{"call-id": part.get("id")},
                            )
                        )
                    elif part.get("type") == "thinking":
                        children.append(_make_entry("reasoning", content=part.get("thinking", "")))
                if children:
                    entry["children"] = children
            entries.append(entry)

    meta["provider"] = _infer_provider(meta["model_id"])
    return entries, meta


def parse_gemini(path):
    """Gemini CLI: single JSON object with messages array.

    Each message maps to ONE entry. Gemini-type messages that contain toolCalls
    or thoughts produce a single assistant entry with typed children.

    Content is passed through as-is (already a string in Gemini).
    Model extracted from: messages[].model on gemini-type messages.
    Provider inferred from: gemini- prefix.
    """
    with open(path) as f:
        data = json.load(f)

    meta = {
        "session_id": data.get("sessionId"),
        "model_id": "unknown",
        "provider": None,
        "cli": "gemini-cli",
        "cli_version": None,
        "start": data.get("startTime"),
        "cwd": None,
        "branch": None,
        "models": set(),
    }
    entries = []

    for msg in data.get("messages", []):
        t = msg.get("type", "user")
        ts = msg.get("timestamp")

        model = msg.get("model")
        if model:
            meta["model_id"] = model
            meta["models"].add(model)

        if t in ("user", "human"):
            entries.append(_make_entry("user", timestamp=ts, content=msg.get("content", ""), id=msg.get("id")))
        else:
            entry = _make_entry(
                "assistant", timestamp=ts, content=msg.get("content", ""), id=msg.get("id"), **{"model-id": model}
            )

            # Build typed children from thoughts and toolCalls
            children = []
            for thought in msg.get("thoughts", []):
                children.append(
                    _make_entry("reasoning", content=thought.get("description", ""), subject=thought.get("subject"))
                )

            for tc in msg.get("toolCalls", []):
                children.append(
                    _make_entry(
                        "tool-call",
                        timestamp=tc.get("timestamp", ts),
                        name=tc.get("name", "unknown"),
                        input=tc.get("args", {}),
                        **{"call-id": tc.get("id")},
                    )
                )
                result = tc.get("result")
                if result is not None:
                    children.append(
                        _make_entry(
                            "tool-result",
                            timestamp=tc.get("timestamp", ts),
                            output=result,
                            status=tc.get("status"),
                            **{"call-id": tc.get("id")},
                        )
                    )

            if children:
                entry["children"] = children
            entries.append(entry)

    meta["provider"] = _infer_provider(meta["model_id"])
    return entries, meta


def parse_codex(path):
    """Codex CLI: JSONL with {timestamp, type, payload} envelope.

    Envelope-level types: session_meta, response_item, event_msg, turn_context.
    Tool calls, reasoning, etc. are nested INSIDE response_item at payload.type:
      payload.type=message (has role) → user/assistant
      payload.type=function_call → tool-call (arguments is a JSON string, not dict)
      payload.type=function_call_output → tool-result
      payload.type=reasoning → reasoning (has encrypted_content for encrypted reasoning)
      payload.type=web_search_call → tool-call (name="web_search")
      payload.type=custom_tool_call → tool-call
      payload.type=custom_tool_call_output → tool-result

    event_msg entries (NOTE: these duplicate response_item for reasoning/messages):
      payload.type=agent_reasoning → reasoning (duplicates response_item reasoning)
      payload.type=token_count → system-event (unique, no response_item equivalent)
      payload.type=user_message → user (may duplicate response_item message)
      payload.type=agent_message → assistant (may duplicate response_item message)

    Model extracted from: payload.model in turn_context (not in session_meta).
    Provider extracted from: payload.model_provider in session_meta.
    """
    with open(path) as f:
        lines = [json.loads(line) for line in f if line.strip()]

    meta = {
        "session_id": None,
        "model_id": "unknown",
        "provider": "unknown",
        "cli": "codex-cli",
        "cli_version": None,
        "start": None,
        "cwd": None,
        "branch": None,
        "models": set(),
    }
    entries = []

    for line in lines:
        ts = line.get("timestamp")
        if not meta["start"] and ts:
            meta["start"] = ts
        payload = line.get("payload", {})
        ltype = line.get("type", "")

        if ltype == "session_meta":
            meta["session_id"] = payload.get("id")
            meta["cli_version"] = payload.get("cli_version")
            meta["cwd"] = payload.get("cwd")
            if payload.get("model"):
                meta["model_id"] = payload["model"]
                meta["models"].add(payload["model"])
            if payload.get("model_provider"):
                meta["provider"] = payload["model_provider"]
            git = payload.get("git", {})
            if git:
                meta["branch"] = git.get("branch")

        elif ltype == "turn_context":
            # Model name lives here when absent from session_meta
            if payload.get("model") and meta["model_id"] == "unknown":
                meta["model_id"] = payload["model"]
                meta["models"].add(payload["model"])

        elif ltype == "response_item":
            ptype = payload.get("type", "")

            if ptype == "message":
                role = payload.get("role", "")
                content = payload.get("content", [])
                if role in ("user", "developer"):
                    entries.append(_make_entry("user", timestamp=ts, content=content))
                elif role == "assistant":
                    entries.append(_make_entry("assistant", timestamp=ts, content=content))

            elif ptype == "function_call":
                entries.append(
                    _make_entry(
                        "tool-call",
                        timestamp=ts,
                        name=payload.get("name", "unknown"),
                        input=payload.get("arguments", {}),
                        **{"call-id": payload.get("call_id")},
                    )
                )

            elif ptype == "function_call_output":
                entries.append(
                    _make_entry(
                        "tool-result",
                        timestamp=ts,
                        output=payload.get("output", ""),
                        **{"call-id": payload.get("call_id")},
                    )
                )

            elif ptype == "reasoning":
                summary = payload.get("summary")
                if isinstance(summary, list):
                    summary = "\n".join(s.get("text", "") for s in summary if isinstance(s, dict))
                entries.append(
                    _make_entry("reasoning", timestamp=ts, content=summary, encrypted=payload.get("encrypted_content"))
                )

            elif ptype == "web_search_call":
                action = payload.get("action", {})
                entries.append(_make_entry("tool-call", timestamp=ts, name="web_search", input=action))

            elif ptype == "custom_tool_call":
                entries.append(
                    _make_entry(
                        "tool-call",
                        timestamp=ts,
                        name=payload.get("name", "unknown"),
                        input=payload.get("input", ""),
                        **{"call-id": payload.get("call_id")},
                    )
                )

            elif ptype == "custom_tool_call_output":
                entries.append(
                    _make_entry(
                        "tool-result",
                        timestamp=ts,
                        output=payload.get("output", ""),
                        **{"call-id": payload.get("call_id")},
                    )
                )

        elif ltype == "event_msg":
            ptype = payload.get("type", "")

            if ptype == "agent_reasoning":
                entries.append(_make_entry("reasoning", timestamp=ts, content=payload.get("text")))

            elif ptype == "token_count":
                entries.append(_make_entry("system-event", timestamp=ts, **{"event-type": "token-count"}))

            elif ptype == "user_message":
                entries.append(_make_entry("user", timestamp=ts, content=payload.get("message")))

            elif ptype == "agent_message":
                entries.append(_make_entry("assistant", timestamp=ts, content=payload.get("message")))

    return entries, meta


def parse_opencode(path):
    """OpenCode: concatenated pretty-printed JSON objects (not strict JSONL).

    Entry types emitted: user, assistant (no content for message-level), tool-call,
    tool-result, reasoning, system-event, patch.

    Tool objects are unified: each "type":"tool" object contains BOTH the
    invocation (state.input) and the result (state.output, state.status) in
    a single object. The parser emits both a tool-call and a tool-result entry
    from each tool object. Timestamps come from state.time.start/end.

    Message-level role objects (role="user"/"assistant") are envelope markers
    with no inline text. Content follows in child objects. These entries are
    emitted without a content field.

    Text parts (type="text") are attributed to user or assistant by looking
    up their messageID against message-level role objects. Role messages
    appear AFTER their child parts in the file, so a two-pass approach is
    used: first collect all role messages, then process parts.

    Model extracted from: modelID on assistant message objects.
    Provider extracted from: providerID on assistant message objects.
    Multi-model: collects all modelID values seen.
    """
    with open(path) as f:
        content = f.read()

    decoder = json.JSONDecoder()
    objects, pos = [], 0
    while pos < len(content):
        stripped = content[pos:].lstrip()
        if not stripped:
            break
        try:
            obj, end = decoder.raw_decode(stripped)
            objects.append(obj)
            pos += (len(content[pos:]) - len(stripped)) + end
        except json.JSONDecodeError:
            break

    meta = {
        "session_id": None,
        "model_id": "unknown",
        "provider": "unknown",
        "cli": "opencode",
        "cli_version": None,
        "start": None,
        "cwd": None,
        "branch": None,
        "models": set(),
    }
    entries = []

    # First pass: collect message-level role objects so we can attribute
    # text parts to the correct role (user vs assistant).  Role messages
    # appear AFTER their child parts in the file, so a lookahead is needed.
    message_roles = {}
    for obj in objects:
        if isinstance(obj, dict) and "role" in obj and "type" not in obj:
            message_roles[obj.get("id")] = obj.get("role")

    for obj in objects:
        if not isinstance(obj, dict):
            continue
        if "worktree" in obj:
            meta["cwd"] = obj.get("worktree")
            time_info = obj.get("time", {})
            if isinstance(time_info, dict) and time_info.get("created"):
                meta["start"] = time_info["created"]
            continue

        if obj.get("sessionID"):
            meta["session_id"] = obj["sessionID"]

        # Message-level objects (role field, no type)
        if "role" in obj and "type" not in obj:
            mid = obj.get("modelID")
            pid = obj.get("providerID")
            if mid:
                meta["model_id"] = mid
                meta["models"].add(mid)
            if pid:
                meta["provider"] = pid
            # Also check nested model object (on user messages)
            model_obj = obj.get("model", {})
            if isinstance(model_obj, dict):
                if model_obj.get("modelID"):
                    meta["models"].add(model_obj["modelID"])
                if model_obj.get("providerID") and meta["provider"] == "unknown":
                    meta["provider"] = model_obj["providerID"]

            ts = obj.get("time", {})
            ts = ts.get("created") if isinstance(ts, dict) else None
            # Content is in child objects, not here — omit content field
            entries.append(_make_entry("user" if obj.get("role") == "user" else "assistant", timestamp=ts))
            continue

        otype = obj.get("type")

        if otype == "text":
            msg_id = obj.get("messageID")
            role = message_roles.get(msg_id, "assistant")
            entry_type = "user" if role == "user" else "assistant"
            entries.append(_make_entry(entry_type, content=obj.get("text", ""), id=obj.get("id")))
        elif otype == "tool":
            state = obj.get("state", {})
            call_id = obj.get("callID")
            tool_ts = None
            time_info = state.get("time", {})
            if isinstance(time_info, dict) and time_info.get("start"):
                tool_ts = time_info["start"]
            entries.append(
                _make_entry(
                    "tool-call",
                    timestamp=tool_ts,
                    name=obj.get("tool", "unknown"),
                    input=state.get("input", {}),
                    id=obj.get("id"),
                    **{"call-id": call_id},
                )
            )
            # OpenCode stores result inline in the same object
            output = state.get("output")
            status = state.get("status")
            if output is not None or status:
                result_ts = None
                if isinstance(time_info, dict) and time_info.get("end"):
                    result_ts = time_info["end"]
                entries.append(
                    _make_entry(
                        "tool-result",
                        timestamp=result_ts,
                        output=output if output is not None else "",
                        status=status,
                        **{"call-id": call_id},
                    )
                )
        elif otype == "patch":
            entries.append(_make_entry("tool-result", id=obj.get("id"), output=obj.get("diff", ""), status="success"))
        elif otype == "reasoning":
            entries.append(_make_entry("reasoning", content=obj.get("text"), id=obj.get("id")))
        elif otype in ("step-start", "step-finish"):
            entries.append(_make_entry("system-event", **{"event-type": otype}))

    return entries, meta


def parse_cursor(path):
    """Cursor: bare JSONL {role, message}. No timestamps, no session ID,
    no entry IDs, no model identification.

    NOTE: Cursor's export format contains zero metadata. This is a known
    limitation — the format stores only role and text content. Session ID
    is generated by the record wrapper. Model/provider are "unknown".
    """
    with open(path) as f:
        lines = [json.loads(line) for line in f if line.strip()]

    meta = {
        "session_id": None,
        "model_id": "unknown",
        "provider": "unknown",
        "cli": "cursor",
        "cli_version": None,
        "start": None,
        "cwd": None,
        "branch": None,
        "models": set(),
    }
    entries = []

    for line in lines:
        role = line.get("role", "user")
        msg = line.get("message", {})
        content = msg.get("content", [])
        entries.append(_make_entry("user" if role == "user" else "assistant", content=content))

    return entries, meta


PARSERS = {
    "claude": parse_claude,
    "gemini": parse_gemini,
    "codex": parse_codex,
    "opencode": parse_opencode,
    "cursor": parse_cursor,
}


# ---------------------------------------------------------------------------
# Wrap parsed entries into minimal verifiable-agent-record for CDDL validation
# ---------------------------------------------------------------------------


def wrap_record(entries, meta):
    """Build the thinnest possible verifiable-agent-record around parsed entries."""
    session_id = meta["session_id"] or str(uuid.uuid4())

    agent_meta = {
        "model-id": meta["model_id"],
        "model-provider": meta["provider"],
    }
    models = sorted(meta.get("models", set()))
    if len(models) > 1:
        agent_meta["models"] = models
    if meta.get("cli"):
        agent_meta["cli-name"] = meta["cli"]
    if meta.get("cli_version"):
        agent_meta["cli-version"] = meta["cli_version"]

    record = {
        "version": "2.0.0-draft",
        "id": session_id,
        "session": {
            "format": "autonomous",
            "session-id": session_id,
            "agent-meta": agent_meta,
            "entries": entries,
        },
    }
    if meta.get("start") is not None:
        record["created"] = meta["start"]
        record["session"]["session-start"] = meta["start"]
    if meta.get("cwd"):
        record["session"]["environment"] = {"working-dir": meta["cwd"]}
    return record


# ---------------------------------------------------------------------------
# CDDL validation
# ---------------------------------------------------------------------------


def validate(schema_path, json_path):
    result = subprocess.run(
        ["cddl", str(schema_path), "validate", str(json_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode == 0, (result.stdout + result.stderr).strip()


def _count_original_items(path, agent):
    """Count items in the original file to detect data loss.

    Returns dict: {total_lines, user_msgs, assistant_msgs, tool_calls,
                   tool_results, reasoning_blocks, other}.
    """
    counts = {"total_lines": 0, "user": 0, "assistant": 0, "tool_call": 0, "tool_result": 0, "reasoning": 0, "other": 0}

    if agent == "gemini":
        with open(path) as f:
            data = json.load(f)
        msgs = data.get("messages", [])
        counts["total_lines"] = len(msgs)
        for msg in msgs:
            t = msg.get("type", "user")
            if t in ("user", "human"):
                counts["user"] += 1
            else:
                # Only count as "assistant" if there's actual text content
                content = _content_to_str(msg.get("content", ""))
                if content:
                    counts["assistant"] += 1
                elif not msg.get("toolCalls") and not msg.get("thoughts"):
                    # Non-user message with no content, no tools, no thoughts
                    counts["assistant"] += 1
            counts["tool_call"] += len(msg.get("toolCalls", []))
            counts["tool_result"] += sum(1 for tc in msg.get("toolCalls", []) if tc.get("result") is not None)
            counts["reasoning"] += len(msg.get("thoughts", []))
        return counts

    if agent == "opencode":
        with open(path) as f:
            content = f.read()
        decoder = json.JSONDecoder()
        # Two-pass: first collect role messages for text-part attribution
        all_objs = []
        msg_roles = {}
        pos = 0
        while pos < len(content):
            stripped = content[pos:].lstrip()
            if not stripped:
                break
            try:
                obj, end = decoder.raw_decode(stripped)
                all_objs.append(obj)
                if isinstance(obj, dict) and "role" in obj and "type" not in obj:
                    msg_roles[obj.get("id")] = obj.get("role")
                pos += (len(content[pos:]) - len(stripped)) + end
            except json.JSONDecodeError:
                break
        for obj in all_objs:
            counts["total_lines"] += 1
            if not isinstance(obj, dict):
                counts["other"] += 1
            elif "worktree" in obj:
                counts["other"] += 1
            elif "role" in obj and "type" not in obj:
                role = obj.get("role", "")
                if role == "user":
                    counts["user"] += 1
                else:
                    counts["assistant"] += 1
            elif obj.get("type") == "text":
                msg_id = obj.get("messageID")
                if msg_roles.get(msg_id) == "user":
                    counts["user"] += 1
                else:
                    counts["assistant"] += 1
            elif obj.get("type") == "tool":
                counts["tool_call"] += 1
                # Tool objects also contain results inline
                state = obj.get("state", {})
                if state.get("output") is not None or state.get("status"):
                    counts["tool_result"] += 1
            elif obj.get("type") == "patch":
                counts["tool_result"] += 1
            elif obj.get("type") == "reasoning":
                counts["reasoning"] += 1
            elif obj.get("type") in ("step-start", "step-finish"):
                counts["other"] += 1
            else:
                counts["other"] += 1
        return counts

    # JSONL formats: claude, codex, cursor
    with open(path) as f:
        lines = [json.loads(line) for line in f if line.strip()]
    counts["total_lines"] = len(lines)

    if agent == "cursor":
        for line in lines:
            role = line.get("role", "user")
            if role == "user":
                counts["user"] += 1
            else:
                counts["assistant"] += 1
        return counts

    if agent == "claude":
        for line in lines:
            msg = line.get("message", {})
            role = msg.get("role")
            if line.get("type") == "queue-operation":
                counts["other"] += 1
            elif role == "user":
                counts["user"] += 1
                # Count children (tool_result blocks inside user content)
                content_parts = msg.get("content", "")
                if isinstance(content_parts, list):
                    for part in content_parts:
                        if isinstance(part, dict) and part.get("type") == "tool_result":
                            counts["tool_result"] += 1
            elif role == "assistant":
                counts["assistant"] += 1
                # Count children (tool_use, thinking blocks inside assistant content)
                content_parts = msg.get("content", [])
                if isinstance(content_parts, list):
                    for part in content_parts:
                        if isinstance(part, dict):
                            if part.get("type") == "tool_use":
                                counts["tool_call"] += 1
                            elif part.get("type") == "thinking":
                                counts["reasoning"] += 1
            elif not role:
                counts["other"] += 1
        return counts

    if agent == "codex":
        for line in lines:
            ltype = line.get("type", "")
            payload = line.get("payload", {})
            if ltype == "session_meta":
                counts["other"] += 1
            elif ltype == "turn_context":
                counts["other"] += 1
            elif ltype == "response_item":
                ptype = payload.get("type", "")
                if ptype == "message":
                    role = payload.get("role", "")
                    if role in ("user", "developer"):
                        counts["user"] += 1
                    elif role == "assistant":
                        counts["assistant"] += 1
                    else:
                        counts["other"] += 1
                elif ptype == "function_call":
                    counts["tool_call"] += 1
                elif ptype == "function_call_output":
                    counts["tool_result"] += 1
                elif ptype == "reasoning":
                    counts["reasoning"] += 1
                elif ptype in ("web_search_call", "custom_tool_call"):
                    counts["tool_call"] += 1
                elif ptype == "custom_tool_call_output":
                    counts["tool_result"] += 1
                else:
                    counts["other"] += 1
            elif ltype == "event_msg":
                ptype = payload.get("type", "")
                if ptype == "agent_reasoning":
                    counts["reasoning"] += 1
                elif ptype == "token_count":
                    counts["other"] += 1
                elif ptype == "user_message":
                    counts["user"] += 1
                elif ptype == "agent_message":
                    counts["assistant"] += 1
                else:
                    counts["other"] += 1
            else:
                counts["other"] += 1
        return counts

    return counts


def _build_report_row(path, agent, entries, meta, record_json):
    """Build a report row for one session file."""
    orig_size = os.path.getsize(path)
    prod_size = len(record_json.encode("utf-8"))

    # Collect all entries including children for counting
    all_entries = []
    for e in entries:
        all_entries.append(e)
        for child in e.get("children", []):
            all_entries.append(child)

    type_counts = {}
    for e in all_entries:
        t = e["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    has_ts = sum(1 for e in all_entries if "timestamp" in e)
    has_id = sum(1 for e in all_entries if "id" in e)
    has_callid = sum(1 for e in all_entries if e["type"] in ("tool-call", "tool-result") and "call-id" in e)
    total_tc = type_counts.get("tool-call", 0) + type_counts.get("tool-result", 0)

    empty_content = sum(1 for e in all_entries if "content" in e and not e["content"])
    no_content = sum(1 for e in all_entries if e["type"] in ("user", "assistant", "reasoning") and "content" not in e)
    has_children = sum(1 for e in entries if "children" in e)

    # Content size in produced record
    content_bytes = 0
    for e in all_entries:
        if "content" in e:
            c = e["content"]
            content_bytes += len(json.dumps(c).encode("utf-8")) if not isinstance(c, str) else len(c.encode("utf-8"))
        if "output" in e:
            o = e["output"]
            content_bytes += len(json.dumps(o).encode("utf-8")) if not isinstance(o, str) else len(o.encode("utf-8"))
        if "input" in e:
            content_bytes += len(json.dumps(e["input"]).encode("utf-8"))

    orig_counts = _count_original_items(path, agent)

    return {
        "file": path.name,
        "agent": agent,
        "orig_size": orig_size,
        "prod_size": prod_size,
        "entries": len(entries),
        "children": len(all_entries) - len(entries),
        "types": type_counts,
        "has_ts": has_ts,
        "has_id": has_id,
        "has_callid": has_callid,
        "total_tc": total_tc,
        "empty_content": empty_content,
        "no_content": no_content,
        "has_children": has_children,
        "content_bytes": content_bytes,
        "meta": meta,
        "orig_counts": orig_counts,
    }


def _print_report(rows):
    """Print the full analysis report."""
    print(f"\n{'=' * 80}")
    print("DETAILED REPORT")
    print(f"{'=' * 80}")

    total_orig = 0
    total_prod = 0

    for r in rows:
        total_orig += r["orig_size"]
        total_prod += r["prod_size"]

        orig_kb = r["orig_size"] / 1024
        prod_kb = r["prod_size"] / 1024
        ratio = r["prod_size"] / r["orig_size"] * 100 if r["orig_size"] else 0
        content_kb = r["content_bytes"] / 1024

        print(f"\n--- {r['file']} ---")
        print(f"  Original: {orig_kb:,.1f} KB  ->  Produced: {prod_kb:,.1f} KB  ({ratio:.1f}%)")
        print(f"  Content payload: {content_kb:,.1f} KB  ({r['content_bytes'] / r['prod_size'] * 100:.0f}% of produced)")
        print(f"  Entries: {r['entries']} (+ {r['children']} children in {r['has_children']} parents)")
        print(f"  Types: {r['types']}")
        print(
            f"  Timestamps: {r['has_ts']}/{r['entries']}"
            f"  IDs: {r['has_id']}/{r['entries']}"
            f"  call-ids: {r['has_callid']}/{r['total_tc']}"
        )
        print(
            f"  Meta: model={r['meta']['model_id']}"
            f"  provider={r['meta']['provider']}"
            f"  session_id={'yes' if r['meta']['session_id'] else 'NO'}"
        )

        if r["empty_content"]:
            print(f"  WARNING: {r['empty_content']} entries with empty string content")
        if r["no_content"]:
            print(f"  NOTE: {r['no_content']} user/assistant/reasoning entries without content field")

        # Data loss detection: compare original counts vs produced
        oc = r["orig_counts"]
        tc = r["types"]
        prod_user = tc.get("user", 0)
        prod_asst = tc.get("assistant", 0)
        prod_tc = tc.get("tool-call", 0)
        prod_tr = tc.get("tool-result", 0)
        prod_rsn = tc.get("reasoning", 0)

        losses = []
        if oc["user"] and prod_user < oc["user"]:
            losses.append(f"user: {prod_user}/{oc['user']}")
        if oc["assistant"] and prod_asst < oc["assistant"]:
            losses.append(f"assistant: {prod_asst}/{oc['assistant']}")
        if oc["tool_call"] and prod_tc < oc["tool_call"]:
            losses.append(f"tool-call: {prod_tc}/{oc['tool_call']}")
        if oc["tool_result"] and prod_tr < oc["tool_result"]:
            losses.append(f"tool-result: {prod_tr}/{oc['tool_result']}")
        if oc["reasoning"] and prod_rsn < oc["reasoning"]:
            losses.append(f"reasoning: {prod_rsn}/{oc['reasoning']}")

        if losses:
            print(f"  DATA LOSS: {', '.join(losses)}")
        else:
            print("  Data coverage: OK (all original items represented)")

        if oc["other"]:
            print(f"  Skipped items: {oc['other']} (metadata/context/lifecycle)")

    print(f"\n{'=' * 80}")
    print("SIZE SUMMARY")
    print(f"{'=' * 80}")
    print(f"  Total original:  {total_orig / 1024 / 1024:.2f} MB")
    print(f"  Total produced:  {total_prod / 1024 / 1024:.2f} MB")
    print(f"  Ratio: {total_prod / total_orig * 100:.1f}%")
    print(f"  Total entries: {sum(r['entries'] for r in rows)} (+ {sum(r['children'] for r in rows)} children)")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=SCHEMA,
        help=f"Path to CDDL schema file (default: {SCHEMA.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=DEFAULT_SESSIONS,
        help=f"Directory containing session files (default: {DEFAULT_SESSIONS.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=0,
        help="Max sessions to validate per agent (default: 0 = all)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full CDDL error output on failures",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print detailed analysis: sizes, entry types, data coverage, loss detection",
    )
    parser.add_argument(
        "--dump-dir",
        type=Path,
        default=None,
        help="Write produced spec-matching JSON records to this directory",
    )
    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"Sessions dir not found: {args.sessions_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.schema.exists():
        print(f"Schema not found: {args.schema}", file=sys.stderr)
        sys.exit(1)

    # Group sessions by agent
    agent_samples = {}
    for s in sorted(args.sessions_dir.iterdir()):
        if not s.name.endswith((".jsonl", ".json")):
            continue
        agent = s.name.split("-")[0]
        if agent not in agent_samples:
            agent_samples[agent] = []
        if args.samples == 0 or len(agent_samples[agent]) < args.samples:
            agent_samples[agent].append(s)

    if args.dump_dir:
        args.dump_dir.mkdir(parents=True, exist_ok=True)

    totals = {"pass": 0, "fail": 0, "skip": 0, "errors": []}
    report_rows = []  # for --report

    for agent, samples in sorted(agent_samples.items()):
        parse_fn = PARSERS.get(agent)
        if not parse_fn:
            print(f"\n[SKIP] {agent}: no parser")
            totals["skip"] += len(samples)
            continue

        print(f"\n=== {agent.upper()} ({len(samples)} samples) ===")
        for sample in samples:
            try:
                entries, meta = parse_fn(sample)
                if not entries:
                    print(f"  [SKIP] {sample.name}: no entries parsed")
                    totals["skip"] += 1
                    continue

                record = wrap_record(entries, meta)
                record_json = json.dumps(record, indent=2)

                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                    f.write(record_json)
                    tmp = f.name

                ok, output = validate(args.schema, tmp)
                os.unlink(tmp)

                if args.dump_dir:
                    out_name = sample.stem + ".spec.json"
                    (args.dump_dir / out_name).write_text(record_json)

                if ok:
                    print(f"  [PASS] {sample.name} ({len(entries)} entries)")
                    totals["pass"] += 1
                else:
                    err = [ln for ln in output.split("\n") if "FAIL" in ln or "error" in ln.lower()]
                    print(f"  [FAIL] {sample.name}")
                    if args.verbose:
                        print(f"         {output[:500]}")
                    else:
                        print(f"         {err[0][:120] if err else output[:120]}")
                    totals["fail"] += 1
                    totals["errors"].append({"agent": agent, "file": sample.name})

                if args.report:
                    report_rows.append(_build_report_row(sample, agent, entries, meta, record_json))

            except Exception as e:
                print(f"  [ERROR] {sample.name}: {e}")
                totals["fail"] += 1
                totals["errors"].append({"agent": agent, "file": sample.name, "error": str(e)})

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {totals['pass']} pass, {totals['fail']} fail, {totals['skip']} skip")
    if totals["errors"]:
        print("\nFailures:")
        for e in totals["errors"]:
            print(f"  [{e['agent']}] {e['file']}")

    if args.report and report_rows:
        _print_report(report_rows)

    sys.exit(1 if totals["fail"] else 0)


if __name__ == "__main__":
    main()
