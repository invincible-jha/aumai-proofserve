"""Core logic for aumai-proofserve."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from .models import ComputationProof, VerificationResult

__all__ = [
    "ProofGenerator",
    "ProofVerifier",
    "ProofStore",
]

_ALGORITHM = "sha256"


def _canonical_json(data: dict[str, Any]) -> bytes:
    """
    Produce a deterministic JSON byte-string for *data*.

    Keys are sorted; non-ASCII characters are preserved.
    """
    return json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _sha256(data: bytes) -> str:
    """Return the lowercase hex SHA-256 digest of *data*."""
    return hashlib.sha256(data).hexdigest()


class ProofGenerator:
    """
    Generates SHA-256 hash-chain proofs for agent computations.

    The proof links input, output, and computation log via a chain hash:
      chain_hash = SHA-256( input_hash || output_hash || computation_hash )

    This ensures that any modification to inputs, outputs, or the
    reasoning log will invalidate the proof.
    """

    def generate_proof(
        self,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        computation_log: str,
        metadata: dict[str, Any] | None = None,
    ) -> ComputationProof:
        """
        Generate a verifiable proof for a computation.

        Args:
            input_data: The input payload (will be canonicalized).
            output_data: The output payload (will be canonicalized).
            computation_log: Free-text log of the computation steps.
            metadata: Optional key-value annotations stored in the proof.

        Returns:
            A ``ComputationProof`` with SHA-256 hashes and a chain hash.
        """
        input_hash = _sha256(_canonical_json(input_data))
        output_hash = _sha256(_canonical_json(output_data))
        computation_hash = _sha256(computation_log.encode("utf-8"))

        # Chain: bind all three hashes together
        chain_input = (input_hash + output_hash + computation_hash).encode(
            "ascii"
        )
        chain_hash = _sha256(chain_input)

        return ComputationProof(
            proof_id=str(uuid.uuid4()),
            input_hash=input_hash,
            output_hash=output_hash,
            computation_hash=computation_hash,
            chain_hash=chain_hash,
            algorithm=_ALGORITHM,
            timestamp=datetime.utcnow(),
            metadata=metadata or {},
        )


class ProofVerifier:
    """Verifies that a ``ComputationProof`` is consistent with input/output."""

    def verify(
        self,
        proof: ComputationProof,
        input_data: dict[str, Any],
        output_data: dict[str, Any],
        computation_log: str = "",
    ) -> VerificationResult:
        """
        Recompute the expected hashes and compare against the stored proof.

        Returns a ``VerificationResult`` with ``valid=True`` only when all
        hashes match exactly.
        """
        expected_input_hash = _sha256(_canonical_json(input_data))
        expected_output_hash = _sha256(_canonical_json(output_data))
        expected_computation_hash = _sha256(
            computation_log.encode("utf-8")
        )
        expected_chain_hash = _sha256(
            (
                expected_input_hash
                + expected_output_hash
                + expected_computation_hash
            ).encode("ascii")
        )

        failures: list[str] = []
        if proof.input_hash != expected_input_hash:
            failures.append(
                f"input_hash mismatch: expected {expected_input_hash!r}, "
                f"got {proof.input_hash!r}"
            )
        if proof.output_hash != expected_output_hash:
            failures.append(
                f"output_hash mismatch: expected {expected_output_hash!r}, "
                f"got {proof.output_hash!r}"
            )
        if computation_log and proof.computation_hash != expected_computation_hash:
            failures.append(
                f"computation_hash mismatch: expected {expected_computation_hash!r}, "
                f"got {proof.computation_hash!r}"
            )
        if proof.chain_hash != expected_chain_hash:
            failures.append(
                f"chain_hash mismatch: expected {expected_chain_hash!r}, "
                f"got {proof.chain_hash!r}"
            )

        if failures:
            return VerificationResult(
                valid=False,
                proof=proof,
                details="Verification failed:\n" + "\n".join(failures),
            )
        return VerificationResult(
            valid=True,
            proof=proof,
            details="All hashes verified successfully.",
        )


class ProofStore:
    """
    In-memory store for ``ComputationProof`` objects.

    Use ``load()`` / ``dump()`` for persistence.
    """

    def __init__(self) -> None:
        self._proofs: dict[str, ComputationProof] = {}

    def save(self, proof: ComputationProof) -> None:
        """Store a proof by its proof_id."""
        self._proofs[proof.proof_id] = proof

    def get(self, proof_id: str) -> ComputationProof:
        """Retrieve a proof by ID."""
        proof = self._proofs.get(proof_id)
        if proof is None:
            raise KeyError(f"No proof found with id {proof_id!r}.")
        return proof

    def list_proofs(self) -> list[ComputationProof]:
        """Return all stored proofs ordered by timestamp."""
        return sorted(
            self._proofs.values(), key=lambda p: p.timestamp
        )

    def delete(self, proof_id: str) -> None:
        """Remove a proof from the store."""
        self._proofs.pop(proof_id, None)

    def dump(self) -> list[dict[str, Any]]:
        """Serialize all proofs to a list of dicts."""
        return [p.model_dump(mode="json") for p in self._proofs.values()]

    def load(self, data: list[dict[str, Any]]) -> None:
        """Restore proofs from a list of serialized dicts."""
        for item in data:
            proof = ComputationProof.model_validate(item)
            self._proofs[proof.proof_id] = proof
