#!/usr/bin/env python3
"""
End-to-end signing validation for verifiable agent records.

For each agent format (claude, gemini, codex, opencode, cursor):
  1. Parse one session file and wrap into a verifiable-agent-record
  2. Generate an ephemeral Ed25519 keypair (in-memory)
  3. Sign with COSE_Sign1 including CWT_Claims in the protected header
  4. CDDL-validate the signed CBOR against agent-conversation.cddl
  5. Verify the signature with detached payload reattachment
  6. Report PASS/FAIL per agent

Exits non-zero if any agent fails.

Usage:
  python3 scripts/validate-signing.py [OPTIONS]

Options:
  --schema PATH        Path to CDDL schema file (default: agent-conversation.cddl)
  --sessions-dir PATH  Directory containing session files (default: examples/sessions/)
  --verbose            Print detailed output per step

Requires: pycose, cbor2, cddl gem
"""

import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pycose.algorithms import EdDSA
from pycose.headers import Algorithm, ContentType
from pycose.keys import OKPKey
from pycose.messages import Sign1Message

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "agent-conversation.cddl"
DEFAULT_SESSIONS = REPO_ROOT / "examples" / "sessions"

# COSE / CWT label constants (mirrors sign-record.py)
TRACE_METADATA_LABEL = 100
CWT_CLAIMS_LABEL = 15
CWT_ISS_LABEL = 1
CWT_SUB_LABEL = 2


# ---------------------------------------------------------------------------
# Import PARSERS and wrap_record from validate-sessions.py
# ---------------------------------------------------------------------------


def _import_validate_sessions():
    """Import validate-sessions.py as a module via importlib."""
    module_path = REPO_ROOT / "scripts" / "validate-sessions.py"
    spec = importlib.util.spec_from_file_location("validate_sessions", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_vs = _import_validate_sessions()
PARSERS = _vs.PARSERS
wrap_record = _vs.wrap_record


# ---------------------------------------------------------------------------
# Signing helpers (self-contained, mirrors sign-record.py logic)
# ---------------------------------------------------------------------------


def _canonical_json(obj):
    """Serialize to canonical JSON: compact, sorted keys, UTF-8."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_trace_metadata(record, json_bytes):
    """Build trace-metadata map from a verifiable-agent-record."""
    session = record.get("session", {})
    agent_meta = session.get("agent-meta", {})

    meta = {
        "session-id": session.get("session-id", record.get("id", "unknown")),
        "agent-vendor": agent_meta.get("model-provider", "unknown"),
        "trace-format": "ietf-vac-v3.0",
        "content-hash": _sha256_hex(json_bytes),
        "content-hash-alg": "sha-256",
    }

    ts_start = session.get("session-start")
    if ts_start is not None:
        meta["timestamp-start"] = ts_start
    else:
        # Fallback to signing time — trace-metadata requires a valid abstract-timestamp
        # (RFC 3339 or epoch number), and some agents (e.g. Cursor) lack timestamps entirely.
        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta["timestamp-start"] = record.get("created", now_utc)

    ts_end = session.get("session-end")
    if ts_end is not None:
        meta["timestamp-end"] = ts_end

    return meta


def _extract_cwt_claims(record):
    """Build CWT_Claims map for the protected header."""
    session = record.get("session", {})
    agent_meta = session.get("agent-meta", {})
    iss = agent_meta.get("model-provider", "unknown")
    sub = session.get("session-id", record.get("id", "unknown"))
    return {CWT_ISS_LABEL: iss, CWT_SUB_LABEL: sub}


def _generate_ephemeral_keypair():
    """Generate an ephemeral Ed25519 keypair, return (private_pem, public_pem)."""
    private_key = Ed25519PrivateKey.generate()
    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = (
        private_key.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return priv_pem, pub_pem


def _sign_record(record, priv_pem):
    """Sign a record with COSE_Sign1 (detached payload). Returns detached CBOR bytes."""
    json_bytes = _canonical_json(record)
    trace_meta = _extract_trace_metadata(record, json_bytes)
    cwt_claims = _extract_cwt_claims(record)
    cose_key = OKPKey.from_pem_private_key(priv_pem)

    msg = Sign1Message(
        phdr={Algorithm: EdDSA, ContentType: "application/json", CWT_CLAIMS_LABEL: cwt_claims},
        uhdr={TRACE_METADATA_LABEL: trace_meta},
        payload=json_bytes,
    )
    msg.key = cose_key

    encoded = msg.encode()

    # Replace payload with null for detached mode
    raw = cbor2.loads(encoded)
    detached_cose = cbor2.CBORTag(18, [raw.value[0], raw.value[1], None, raw.value[3]])
    return cbor2.dumps(detached_cose)


def _cddl_validate(schema_path, cbor_bytes):
    """Validate CBOR bytes against the CDDL schema. Returns (ok, output)."""
    with tempfile.NamedTemporaryFile(suffix=".cbor", delete=False) as f:
        f.write(cbor_bytes)
        tmp = f.name
    try:
        result = subprocess.run(
            ["cddl", str(schema_path), "validate", tmp],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    finally:
        os.unlink(tmp)


def _verify_signature(sig_bytes, record, pub_pem):
    """Verify a COSE_Sign1 signature against a record. Returns (ok, error_msg)."""
    json_bytes = _canonical_json(record)
    cose_key = OKPKey.from_pem_public_key(pub_pem)

    decoded = Sign1Message.decode(sig_bytes)
    decoded.key = cose_key
    decoded.payload = json_bytes

    try:
        valid = decoded.verify_signature()
    except Exception as e:
        return False, f"Signature verification error: {e}"

    if not valid:
        return False, "Signature is invalid"

    # Verify content hash
    trace_meta = decoded.uhdr.get(TRACE_METADATA_LABEL, {})
    expected_hash = trace_meta.get("content-hash")
    if expected_hash:
        actual_hash = _sha256_hex(json_bytes)
        if actual_hash != expected_hash:
            return False, f"Content hash mismatch: expected {expected_hash}, got {actual_hash}"

    return True, None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def _pick_one_session(sessions_dir, agent):
    """Pick the first session file (alphabetically) for the given agent."""
    candidates = sorted(
        p for p in sessions_dir.iterdir() if p.name.startswith(agent + "-") and p.name.endswith((".jsonl", ".json"))
    )
    return candidates[0] if candidates else None


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
    parser.add_argument("--verbose", action="store_true", help="Print detailed output per step")
    args = parser.parse_args()

    if not args.sessions_dir.exists():
        print(f"Sessions dir not found: {args.sessions_dir}", file=sys.stderr)
        sys.exit(1)
    if not args.schema.exists():
        print(f"Schema not found: {args.schema}", file=sys.stderr)
        sys.exit(1)

    print("End-to-end signing validation")
    print(f"Schema: {args.schema}")
    print(f"Sessions: {args.sessions_dir}")
    print()

    # Generate one ephemeral keypair for the entire run
    priv_pem, pub_pem = _generate_ephemeral_keypair()

    results = {}
    for agent in sorted(PARSERS.keys()):
        session_path = _pick_one_session(args.sessions_dir, agent)
        if not session_path:
            print(f"  [{agent}] SKIP: no session files found")
            results[agent] = "skip"
            continue

        print(f"  [{agent}] {session_path.name}")

        try:
            # 1. Parse + wrap
            parse_fn = PARSERS[agent]
            entries, meta = parse_fn(session_path)
            if not entries:
                print("    SKIP: no entries parsed")
                results[agent] = "skip"
                continue
            record = wrap_record(entries, meta)
            if args.verbose:
                print(f"    Parsed: {len(entries)} entries")

            # 2. Sign
            sig_bytes = _sign_record(record, priv_pem)
            if args.verbose:
                print(f"    Signed: {len(sig_bytes)} bytes CBOR")

            # 3. CDDL-validate the signed CBOR
            ok, cddl_output = _cddl_validate(args.schema, sig_bytes)
            if not ok:
                print("    FAIL: CDDL validation of signed record")
                if args.verbose:
                    print(f"    {cddl_output[:300]}")
                results[agent] = "fail"
                continue
            if args.verbose:
                print("    CDDL: PASS")

            # 4. Verify signature
            ok, err = _verify_signature(sig_bytes, record, pub_pem)
            if not ok:
                print(f"    FAIL: {err}")
                results[agent] = "fail"
                continue
            if args.verbose:
                print("    Verify: PASS")

            print("    PASS (sign + CDDL-validate + verify)")
            results[agent] = "pass"

        except Exception as e:
            print(f"    ERROR: {e}")
            results[agent] = "fail"

    # Summary
    passes = sum(1 for v in results.values() if v == "pass")
    fails = sum(1 for v in results.values() if v == "fail")
    skips = sum(1 for v in results.values() if v == "skip")

    print(f"\n{'=' * 60}")
    print(f"RESULTS: {passes} pass, {fails} fail, {skips} skip")
    if fails:
        print("\nFailed agents:")
        for agent, status in sorted(results.items()):
            if status == "fail":
                print(f"  {agent}")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
