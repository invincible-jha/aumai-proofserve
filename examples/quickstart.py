"""aumai-proofserve quickstart — verifiable computation proofs for agent outputs.

This file demonstrates:
  1. Generating a SHA-256 hash-chain proof for an agent computation.
  2. Verifying a valid proof against the original inputs and outputs.
  3. Detecting tampered output — the verifier reports which hash failed.
  4. Storing and retrieving proofs in-memory via ProofStore.
  5. Serialising and reloading proofs for cross-process persistence.

Run directly:
    python examples/quickstart.py

Install first:
    pip install aumai-proofserve
"""

from __future__ import annotations

import json

from aumai_proofserve.core import ProofGenerator, ProofStore, ProofVerifier
from aumai_proofserve.models import ComputationProof, VerificationResult


# ---------------------------------------------------------------------------
# Shared computation fixture used across all demos
# ---------------------------------------------------------------------------

AGENT_INPUT: dict[str, object] = {
    "task": "Summarise Q4 financial report",
    "document_id": "fin-report-2025-q4",
    "model": "claude-opus-4-6",
    "temperature": 0.2,
}

AGENT_OUTPUT: dict[str, object] = {
    "summary": (
        "Revenue grew 18% YoY to $4.2B.  Operating margin expanded by 2.3 pp "
        "to 31.1%.  Free cash flow reached $980M.  Q1 2026 guidance projects "
        "continued growth of 12-15%."
    ),
    "word_count": 38,
    "confidence": 0.91,
}

COMPUTATION_LOG = (
    "Step 1: Retrieved document fin-report-2025-q4 (12,400 tokens).\n"
    "Step 2: Applied extractive summarisation with temperature=0.2.\n"
    "Step 3: Validated output length (word_count=38, within 20-100 range).\n"
    "Step 4: Computed confidence score via NLI model: 0.91.\n"
    "Step 5: Returned structured JSON output."
)


# ---------------------------------------------------------------------------
# Demo 1: Generate a computation proof
# ---------------------------------------------------------------------------

def demo_generate_proof() -> ComputationProof:
    """Generate a verifiable proof that cryptographically binds input, output,
    and reasoning log via a SHA-256 hash chain.

    The chain hash is computed as:
        SHA-256(input_hash || output_hash || computation_hash)

    Any modification to any of the three components will change chain_hash
    and make the tampering detectable at verification time.
    """
    print("\n--- Demo 1: Generate a Computation Proof ---")

    generator = ProofGenerator()
    proof = generator.generate_proof(
        input_data=AGENT_INPUT,
        output_data=AGENT_OUTPUT,
        computation_log=COMPUTATION_LOG,
        metadata={
            "agent_version": "1.4.2",
            "environment": "production",
            "requested_by": "audit-system",
        },
    )

    print(f"  proof_id         : {proof.proof_id}")
    print(f"  timestamp        : {proof.timestamp.isoformat()}")
    print(f"  algorithm        : {proof.algorithm}")
    print(f"  input_hash       : {proof.input_hash[:20]}...")
    print(f"  output_hash      : {proof.output_hash[:20]}...")
    print(f"  computation_hash : {proof.computation_hash[:20]}...")
    print(f"  chain_hash       : {proof.chain_hash[:20]}...")
    print(f"  metadata         : {proof.metadata}")

    return proof


# ---------------------------------------------------------------------------
# Demo 2: Verify a valid proof
# ---------------------------------------------------------------------------

def demo_verify_valid_proof(proof: ComputationProof) -> None:
    """Verify the proof against the unmodified inputs, outputs, and log.

    ProofVerifier.verify() recomputes all four hashes from the raw data and
    compares them against the stored proof.  VerificationResult.valid is True
    only when every hash matches exactly.
    """
    print("\n--- Demo 2: Verify a Valid Proof ---")

    verifier = ProofVerifier()
    result: VerificationResult = verifier.verify(
        proof=proof,
        input_data=AGENT_INPUT,
        output_data=AGENT_OUTPUT,
        computation_log=COMPUTATION_LOG,
    )

    print(f"  valid   : {result.valid}")
    print(f"  details : {result.details}")


# ---------------------------------------------------------------------------
# Demo 3: Detect tampering — modified output
# ---------------------------------------------------------------------------

def demo_detect_tampered_output(proof: ComputationProof) -> None:
    """Show that the verifier detects a modified output payload.

    An adversary who alters the summary text changes output_hash, which then
    causes chain_hash to diverge from the recorded value.  The verifier
    surfaces both mismatches so auditors know exactly what changed.
    """
    print("\n--- Demo 3: Detect Tampered Output ---")

    tampered_output: dict[str, object] = {
        **AGENT_OUTPUT,
        "summary": (
            "Revenue declined 5% YoY.  Operating margin contracted significantly.  "
            "Guidance was withdrawn due to macro uncertainty."
        ),
        "confidence": 0.99,
    }

    verifier = ProofVerifier()
    result: VerificationResult = verifier.verify(
        proof=proof,
        input_data=AGENT_INPUT,
        output_data=tampered_output,
        computation_log=COMPUTATION_LOG,
    )

    print(f"  valid   : {result.valid}  (expected: False)")
    # Show only the first reported failure line for conciseness.
    failure_lines = result.details.strip().split("\n")
    first_failure = failure_lines[1] if len(failure_lines) > 1 else result.details
    print(f"  failure : {first_failure}")


# ---------------------------------------------------------------------------
# Demo 4: Store and retrieve proofs in-memory
# ---------------------------------------------------------------------------

def demo_proof_store(proof: ComputationProof) -> None:
    """Save proofs to ProofStore, then retrieve and list all stored entries.

    ProofStore is an in-memory registry keyed by proof_id.  Use dump() and
    load() for persistence across process restarts (shown in Demo 5).
    """
    print("\n--- Demo 4: ProofStore — Save, List, and Retrieve ---")

    generator = ProofGenerator()
    store = ProofStore()

    # Save the proof from Demo 1.
    store.save(proof)

    # Generate and save a second proof for a different agent computation.
    second_proof = generator.generate_proof(
        input_data={"task": "classify_intent", "text": "Book a flight to Mumbai"},
        output_data={"intent": "travel_booking", "confidence": 0.96},
        computation_log="Step 1: Tokenised input.\nStep 2: Ran classifier.\n",
        metadata={"agent": "intent-classifier-v2"},
    )
    store.save(second_proof)

    # List all proofs ordered by timestamp.
    all_proofs = store.list_proofs()
    print(f"  Proofs in store: {len(all_proofs)}")
    for stored_proof in all_proofs:
        print(
            f"    {stored_proof.proof_id[:12]}...  "
            f"ts={stored_proof.timestamp.strftime('%H:%M:%S')}  "
            f"meta={stored_proof.metadata}"
        )

    # Retrieve by ID and confirm the chain_hash survived the round-trip.
    retrieved = store.get(proof.proof_id)
    hashes_match = retrieved.chain_hash == proof.chain_hash
    print(f"\n  Retrieved proof {proof.proof_id[:12]}... — chain_hash matches: {hashes_match}")


# ---------------------------------------------------------------------------
# Demo 5: Serialise and reload proofs
# ---------------------------------------------------------------------------

def demo_serialise_and_reload(proof: ComputationProof) -> None:
    """Dump proofs to JSON-serialisable dicts and reload into a fresh ProofStore.

    This pattern supports writing proofs to a database, S3 bucket, or any
    JSON-capable storage backend and rehydrating them later for audit or
    re-verification without access to the original agent runtime.
    """
    print("\n--- Demo 5: Serialise and Reload ---")

    store = ProofStore()
    store.save(proof)

    # dump() returns a list of JSON-serialisable dicts.
    serialised: list[dict[str, object]] = store.dump()
    raw_json: str = json.dumps(serialised, default=str, indent=2)

    byte_count = len(raw_json.encode("utf-8"))
    print(f"  Serialised to {byte_count} bytes of JSON.")
    # Print a short preview of the first record.
    preview = raw_json[:180].replace("\n", "\n  ")
    print(f"  Preview:\n  {preview}...")

    # Reload into a fresh store instance (simulates a new process).
    fresh_store = ProofStore()
    fresh_store.load(serialised)

    reloaded_proof = fresh_store.get(proof.proof_id)
    verifier = ProofVerifier()
    result: VerificationResult = verifier.verify(
        proof=reloaded_proof,
        input_data=AGENT_INPUT,
        output_data=AGENT_OUTPUT,
        computation_log=COMPUTATION_LOG,
    )

    print(f"\n  Reload + verify: valid={result.valid}  details='{result.details}'")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run all five proofserve quickstart demonstrations."""
    print("=" * 60)
    print("aumai-proofserve quickstart")
    print("Verifiable computation proofs for agent outputs")
    print("=" * 60)

    proof = demo_generate_proof()
    demo_verify_valid_proof(proof)
    demo_detect_tampered_output(proof)
    demo_proof_store(proof)
    demo_serialise_and_reload(proof)

    print("\nDone.")


if __name__ == "__main__":
    main()
