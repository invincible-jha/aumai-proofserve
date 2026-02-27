"""Shared test fixtures for aumai-proofserve."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from aumai_proofserve.core import ProofGenerator, ProofStore, ProofVerifier
from aumai_proofserve.models import ComputationProof, VerificationResult


# ---------------------------------------------------------------------------
# Canonical data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_input_data() -> dict[str, Any]:
    return {"query": "What is the capital of France?", "context_length": 512}


@pytest.fixture()
def sample_output_data() -> dict[str, Any]:
    return {"answer": "Paris", "confidence": 0.99, "tokens_used": 128}


@pytest.fixture()
def sample_computation_log() -> str:
    return "Step 1: tokenize input\nStep 2: run inference\nStep 3: decode output"


# ---------------------------------------------------------------------------
# Core object fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def generator() -> ProofGenerator:
    return ProofGenerator()


@pytest.fixture()
def verifier() -> ProofVerifier:
    return ProofVerifier()


@pytest.fixture()
def proof_store() -> ProofStore:
    return ProofStore()


@pytest.fixture()
def sample_proof(
    generator: ProofGenerator,
    sample_input_data: dict[str, Any],
    sample_output_data: dict[str, Any],
    sample_computation_log: str,
) -> ComputationProof:
    return generator.generate_proof(
        input_data=sample_input_data,
        output_data=sample_output_data,
        computation_log=sample_computation_log,
    )


# ---------------------------------------------------------------------------
# Filesystem helpers for CLI tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory."""
    return tmp_path


@pytest.fixture()
def input_json_file(tmp_path: Path, sample_input_data: dict[str, Any]) -> Path:
    p = tmp_path / "input.json"
    p.write_text(json.dumps(sample_input_data), encoding="utf-8")
    return p


@pytest.fixture()
def output_json_file(tmp_path: Path, sample_output_data: dict[str, Any]) -> Path:
    p = tmp_path / "output.json"
    p.write_text(json.dumps(sample_output_data), encoding="utf-8")
    return p


@pytest.fixture()
def log_file(tmp_path: Path, sample_computation_log: str) -> Path:
    p = tmp_path / "log.txt"
    p.write_text(sample_computation_log, encoding="utf-8")
    return p


@pytest.fixture()
def proof_json_file(
    tmp_path: Path,
    sample_proof: ComputationProof,
) -> Path:
    p = tmp_path / "proof.json"
    p.write_text(sample_proof.model_dump_json(indent=2), encoding="utf-8")
    return p
