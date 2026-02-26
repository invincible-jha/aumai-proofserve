"""Pydantic models for aumai-proofserve."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "ComputationProof",
    "VerificationResult",
]


class ComputationProof(BaseModel):
    """Cryptographic proof of a computation's inputs, outputs, and steps."""

    proof_id: str
    input_hash: str   # SHA-256 hex of canonical input JSON
    output_hash: str  # SHA-256 hex of canonical output JSON
    computation_hash: str  # SHA-256 hex of the computation log
    chain_hash: str   # SHA-256 hex of input_hash + output_hash + computation_hash
    algorithm: str = "sha256"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """Result of verifying a ComputationProof against input/output data."""

    valid: bool
    proof: ComputationProof
    details: str
