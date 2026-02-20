#!/usr/bin/env python3
"""
Sign and verify agent conversation records with COSE_Sign1 (RFC 9052).

Produces detached-payload COSE_Sign1 signatures compatible with the
`signed-agent-record` type defined in agent-conversation.cddl Section 9.
The JSON record file stays separate; the .sig.cbor file contains only the
cryptographic envelope (protected header, unprotected trace-metadata,
null payload, signature bytes).

Algorithm: Ed25519 (EdDSA) — fast, small signatures, used by RATS/SCITT.

Usage:
  # Generate Ed25519 keypair
  python3 scripts/sign-record.py keygen --out /tmp/vac-keys/

  # Sign a record (detached payload)
  python3 scripts/sign-record.py sign \\
    --key /tmp/vac-keys/signing-key.pem \\
    --record /tmp/vac-produced/claude-opus-4-6.spec.json \\
    --out /tmp/vac-produced/claude-opus-4-6.sig.cbor

  # Verify a signature
  python3 scripts/sign-record.py verify \\
    --key /tmp/vac-keys/signing-key.pub.pem \\
    --sig /tmp/vac-produced/claude-opus-4-6.sig.cbor \\
    --record /tmp/vac-produced/claude-opus-4-6.spec.json

Requires: pycose, cbor2 (see requirements.txt)
"""

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

import cbor2
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pycose.algorithms import EdDSA
from pycose.headers import Algorithm, ContentType
from pycose.keys import OKPKey
from pycose.messages import Sign1Message

TRACE_METADATA_LABEL = 100  # Private-use label per CDDL Section 9
CWT_CLAIMS_LABEL = 15  # COSE label for CWT_Claims in protected header
CWT_ISS_LABEL = 1  # CWT issuer claim
CWT_SUB_LABEL = 2  # CWT subject claim


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _canonical_json(obj):
    """Serialize to canonical JSON: compact, sorted keys, UTF-8."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_cwt_claims(record, issuer_override=None, subject_override=None):
    """Build CWT_Claims map for the protected header.

    Defaults: iss = model-provider (e.g. "anthropic"), sub = session-id.
    """
    session = record.get("session", {})
    agent_meta = session.get("agent-meta", {})

    iss = issuer_override or agent_meta.get("model-provider", "unknown")
    sub = subject_override or session.get("session-id", record.get("id", "unknown"))

    return {CWT_ISS_LABEL: iss, CWT_SUB_LABEL: sub}


def _extract_trace_metadata(record, json_bytes):
    """Build trace-metadata map from a verifiable-agent-record JSON object."""
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


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_keygen(args):
    """Generate an Ed25519 keypair and write PEM files."""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    private_key = Ed25519PrivateKey.generate()

    priv_path = out_dir / "signing-key.pem"
    priv_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    priv_path.write_bytes(priv_pem)

    pub_path = out_dir / "signing-key.pub.pem"
    pub_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    pub_path.write_bytes(pub_pem)

    print(f"Private key: {priv_path}")
    print(f"Public key:  {pub_path}")
    print("Algorithm:   Ed25519 (EdDSA)")


def cmd_sign(args):
    """Sign a JSON record with COSE_Sign1 (detached payload)."""
    # Read and canonicalize the record
    record_path = Path(args.record)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    json_bytes = _canonical_json(record)

    # Build trace-metadata for unprotected header
    trace_meta = _extract_trace_metadata(record, json_bytes)

    # Load signing key
    key_pem = Path(args.key).read_text(encoding="utf-8")
    cose_key = OKPKey.from_pem_private_key(key_pem)

    # Build CWT_Claims for protected header (SCITT-required)
    cwt_claims = _extract_cwt_claims(record, args.issuer, args.subject)

    # Build COSE_Sign1 message
    msg = Sign1Message(
        phdr={Algorithm: EdDSA, ContentType: "application/json", CWT_CLAIMS_LABEL: cwt_claims},
        uhdr={TRACE_METADATA_LABEL: trace_meta},
        payload=json_bytes,
    )
    msg.key = cose_key

    # Encode (computes signature over the actual payload)
    encoded = msg.encode()

    # Manually replace payload with null for detached mode
    # pycose doesn't properly null out the payload in CBOR output
    raw = cbor2.loads(encoded)
    detached_cose = cbor2.CBORTag(18, [raw.value[0], raw.value[1], None, raw.value[3]])
    detached_bytes = cbor2.dumps(detached_cose)

    # Write output
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(detached_bytes)

    print(f"Signature:    {out_path}")
    print(f"Payload hash: {trace_meta['content-hash']}")
    print(f"Session ID:   {trace_meta['session-id']}")
    print(f"Agent vendor: {trace_meta['agent-vendor']}")
    print(f"Payload size: {len(json_bytes)} bytes (detached)")


def cmd_verify(args):
    """Verify a COSE_Sign1 signature against a JSON record."""
    # Read the signature file
    sig_path = Path(args.sig)
    sig_bytes = sig_path.read_bytes()

    # Read and canonicalize the record (detached payload)
    record_path = Path(args.record)
    record = json.loads(record_path.read_text(encoding="utf-8"))
    json_bytes = _canonical_json(record)

    # Load public key
    key_pem = Path(args.key).read_text(encoding="utf-8")
    cose_key = OKPKey.from_pem_public_key(key_pem)

    # Decode COSE_Sign1 and attach the detached payload
    decoded = Sign1Message.decode(sig_bytes)
    decoded.key = cose_key
    decoded.payload = json_bytes

    # Verify signature
    try:
        valid = decoded.verify_signature()
    except Exception as e:
        print(f"FAIL: Signature verification error: {e}")
        sys.exit(1)

    if not valid:
        print("FAIL: Signature is invalid")
        sys.exit(1)

    # Extract and display trace-metadata
    trace_meta = decoded.uhdr.get(TRACE_METADATA_LABEL, {})

    # Verify content hash if present
    hash_ok = True
    expected_hash = trace_meta.get("content-hash")
    if expected_hash:
        actual_hash = _sha256_hex(json_bytes)
        hash_ok = actual_hash == expected_hash
        if not hash_ok:
            print("FAIL: Content hash mismatch")
            print(f"  Expected: {expected_hash}")
            print(f"  Actual:   {actual_hash}")
            sys.exit(1)

    # Extract CWT_Claims from protected header
    phdr = decoded.phdr
    cwt_claims = phdr.get(CWT_CLAIMS_LABEL, {})

    print("PASS: Signature verified")
    print(f"  CWT Issuer:   {cwt_claims.get(CWT_ISS_LABEL, 'N/A')}")
    print(f"  CWT Subject:  {cwt_claims.get(CWT_SUB_LABEL, 'N/A')}")
    print(f"  Session ID:   {trace_meta.get('session-id', 'N/A')}")
    print(f"  Agent vendor: {trace_meta.get('agent-vendor', 'N/A')}")
    print(f"  Trace format: {trace_meta.get('trace-format', 'N/A')}")
    print(f"  Timestamp:    {trace_meta.get('timestamp-start', 'N/A')}")
    print(f"  Content hash: {expected_hash or 'not present'} {'(verified)' if expected_hash and hash_ok else ''}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # keygen
    kg = sub.add_parser("keygen", help="Generate Ed25519 keypair")
    kg.add_argument("--out", required=True, help="Output directory for PEM files")

    # sign
    sg = sub.add_parser("sign", help="Sign a record with COSE_Sign1 (detached payload)")
    sg.add_argument("--key", required=True, help="Path to private key PEM")
    sg.add_argument("--record", required=True, help="Path to JSON record file")
    sg.add_argument("--out", required=True, help="Output path for .sig.cbor file")
    sg.add_argument("--issuer", help="CWT issuer (defaults to model-provider)")
    sg.add_argument("--subject", help="CWT subject (defaults to session-id)")

    # verify
    vf = sub.add_parser("verify", help="Verify a COSE_Sign1 signature")
    vf.add_argument("--key", required=True, help="Path to public key PEM")
    vf.add_argument("--sig", required=True, help="Path to .sig.cbor signature file")
    vf.add_argument("--record", required=True, help="Path to JSON record file")

    args = parser.parse_args()

    if args.command == "keygen":
        cmd_keygen(args)
    elif args.command == "sign":
        cmd_sign(args)
    elif args.command == "verify":
        cmd_verify(args)


if __name__ == "__main__":
    main()
