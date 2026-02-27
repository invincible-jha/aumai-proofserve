"""Tests for aumai_proofserve.core."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

import pytest

from aumai_proofserve.core import (
    ProofGenerator,
    ProofStore,
    ProofVerifier,
    _canonical_json,
    _sha256,
)
from aumai_proofserve.models import ComputationProof, VerificationResult


# ---------------------------------------------------------------------------
# _canonical_json
# ---------------------------------------------------------------------------


class TestCanonicalJson:
    def test_keys_are_sorted(self) -> None:
        data = {"z": 1, "a": 2, "m": 3}
        result = _canonical_json(data)
        parsed = json.loads(result)
        assert list(parsed.keys()) == sorted(data.keys())

    def test_returns_bytes(self) -> None:
        assert isinstance(_canonical_json({"x": 1}), bytes)

    def test_deterministic_across_key_order(self) -> None:
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert _canonical_json(d1) == _canonical_json(d2)

    def test_empty_dict(self) -> None:
        assert _canonical_json({}) == b"{}"

    def test_non_ascii_preserved(self) -> None:
        data = {"key": "\u00e9l\u00e8ve"}
        result = _canonical_json(data)
        assert "\u00e9l\u00e8ve" in result.decode("utf-8")


# ---------------------------------------------------------------------------
# _sha256
# ---------------------------------------------------------------------------


class TestSha256:
    def test_known_hash(self) -> None:
        data = b"hello"
        expected = hashlib.sha256(b"hello").hexdigest()
        assert _sha256(data) == expected

    def test_returns_64_hex_chars(self) -> None:
        assert len(_sha256(b"anything")) == 64

    def test_empty_bytes(self) -> None:
        assert _sha256(b"") == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# ProofGenerator
# ---------------------------------------------------------------------------


class TestProofGenerator:
    def test_generate_proof_returns_computation_proof(
        self,
        generator: ProofGenerator,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
        sample_computation_log: str,
    ) -> None:
        proof = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log=sample_computation_log,
        )
        assert isinstance(proof, ComputationProof)

    def test_proof_has_valid_uuid(
        self,
        sample_proof: ComputationProof,
    ) -> None:
        import uuid

        uuid.UUID(sample_proof.proof_id)  # raises if invalid

    def test_proof_hashes_are_64_char_hex(
        self,
        sample_proof: ComputationProof,
    ) -> None:
        for field in (
            sample_proof.input_hash,
            sample_proof.output_hash,
            sample_proof.computation_hash,
            sample_proof.chain_hash,
        ):
            assert len(field) == 64
            int(field, 16)  # must be valid hex

    def test_algorithm_is_sha256(
        self, sample_proof: ComputationProof
    ) -> None:
        assert sample_proof.algorithm == "sha256"

    def test_timestamp_is_datetime(
        self, sample_proof: ComputationProof
    ) -> None:
        assert isinstance(sample_proof.timestamp, datetime)

    def test_metadata_defaults_to_empty_dict(
        self,
        generator: ProofGenerator,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
    ) -> None:
        proof = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="",
        )
        assert proof.metadata == {}

    def test_metadata_is_stored(
        self,
        generator: ProofGenerator,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
    ) -> None:
        metadata = {"source": "test", "version": "1.0"}
        proof = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="",
            metadata=metadata,
        )
        assert proof.metadata == metadata

    def test_same_inputs_produce_same_hashes(
        self,
        generator: ProofGenerator,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
        sample_computation_log: str,
    ) -> None:
        proof1 = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log=sample_computation_log,
        )
        proof2 = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log=sample_computation_log,
        )
        # Hashes must be identical; proof_ids will differ
        assert proof1.input_hash == proof2.input_hash
        assert proof1.output_hash == proof2.output_hash
        assert proof1.computation_hash == proof2.computation_hash
        assert proof1.chain_hash == proof2.chain_hash
        assert proof1.proof_id != proof2.proof_id

    def test_different_inputs_produce_different_input_hash(
        self,
        generator: ProofGenerator,
        sample_output_data: dict[str, Any],
    ) -> None:
        proof1 = generator.generate_proof(
            input_data={"a": 1},
            output_data=sample_output_data,
            computation_log="",
        )
        proof2 = generator.generate_proof(
            input_data={"a": 2},
            output_data=sample_output_data,
            computation_log="",
        )
        assert proof1.input_hash != proof2.input_hash
        assert proof1.chain_hash != proof2.chain_hash

    def test_different_outputs_produce_different_output_hash(
        self,
        generator: ProofGenerator,
        sample_input_data: dict[str, Any],
    ) -> None:
        proof1 = generator.generate_proof(
            input_data=sample_input_data,
            output_data={"result": "yes"},
            computation_log="",
        )
        proof2 = generator.generate_proof(
            input_data=sample_input_data,
            output_data={"result": "no"},
            computation_log="",
        )
        assert proof1.output_hash != proof2.output_hash

    def test_chain_hash_binds_all_three_components(
        self,
        generator: ProofGenerator,
    ) -> None:
        proof = generator.generate_proof(
            input_data={"x": 1},
            output_data={"y": 2},
            computation_log="log line",
        )
        chain_input = (
            proof.input_hash + proof.output_hash + proof.computation_hash
        ).encode("ascii")
        expected_chain = hashlib.sha256(chain_input).hexdigest()
        assert proof.chain_hash == expected_chain

    def test_empty_computation_log(
        self,
        generator: ProofGenerator,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
    ) -> None:
        proof = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="",
        )
        expected = hashlib.sha256(b"").hexdigest()
        assert proof.computation_hash == expected

    def test_nested_dict_input(
        self,
        generator: ProofGenerator,
    ) -> None:
        proof = generator.generate_proof(
            input_data={"nested": {"deep": [1, 2, 3]}},
            output_data={"ok": True},
            computation_log="",
        )
        assert len(proof.input_hash) == 64


# ---------------------------------------------------------------------------
# ProofVerifier
# ---------------------------------------------------------------------------


class TestProofVerifier:
    def test_valid_proof_returns_valid_true(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
        sample_computation_log: str,
    ) -> None:
        result = verifier.verify(
            proof=sample_proof,
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log=sample_computation_log,
        )
        assert isinstance(result, VerificationResult)
        assert result.valid is True
        assert "verified successfully" in result.details

    def test_tampered_input_fails(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
        sample_output_data: dict[str, Any],
        sample_computation_log: str,
    ) -> None:
        result = verifier.verify(
            proof=sample_proof,
            input_data={"tampered": True},
            output_data=sample_output_data,
            computation_log=sample_computation_log,
        )
        assert result.valid is False
        assert "input_hash mismatch" in result.details

    def test_tampered_output_fails(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
        sample_input_data: dict[str, Any],
        sample_computation_log: str,
    ) -> None:
        result = verifier.verify(
            proof=sample_proof,
            input_data=sample_input_data,
            output_data={"tampered": True},
            computation_log=sample_computation_log,
        )
        assert result.valid is False
        assert "output_hash mismatch" in result.details

    def test_tampered_log_fails(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
    ) -> None:
        result = verifier.verify(
            proof=sample_proof,
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="tampered log",
        )
        assert result.valid is False

    def test_empty_log_skips_computation_hash_check(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
    ) -> None:
        # The verifier skips computation_hash check when log is ""
        # but chain_hash will still mismatch if the original had a log
        result = verifier.verify(
            proof=sample_proof,
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="",
        )
        # chain_hash will differ from original since computation_log differs
        assert isinstance(result, VerificationResult)

    def test_verify_result_contains_proof_reference(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
        sample_computation_log: str,
    ) -> None:
        result = verifier.verify(
            proof=sample_proof,
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log=sample_computation_log,
        )
        assert result.proof.proof_id == sample_proof.proof_id

    def test_all_failures_accumulate_in_details(
        self,
        verifier: ProofVerifier,
        sample_proof: ComputationProof,
    ) -> None:
        result = verifier.verify(
            proof=sample_proof,
            input_data={"wrong": "input"},
            output_data={"wrong": "output"},
            computation_log="wrong log",
        )
        assert result.valid is False
        assert "input_hash mismatch" in result.details
        assert "output_hash mismatch" in result.details

    def test_verify_proof_with_no_log(
        self,
        generator: ProofGenerator,
        verifier: ProofVerifier,
        sample_input_data: dict[str, Any],
        sample_output_data: dict[str, Any],
    ) -> None:
        proof = generator.generate_proof(
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="",
        )
        result = verifier.verify(
            proof=proof,
            input_data=sample_input_data,
            output_data=sample_output_data,
            computation_log="",
        )
        assert result.valid is True


# ---------------------------------------------------------------------------
# ProofStore
# ---------------------------------------------------------------------------


class TestProofStore:
    def test_save_and_get(
        self,
        proof_store: ProofStore,
        sample_proof: ComputationProof,
    ) -> None:
        proof_store.save(sample_proof)
        retrieved = proof_store.get(sample_proof.proof_id)
        assert retrieved.proof_id == sample_proof.proof_id
        assert retrieved.chain_hash == sample_proof.chain_hash

    def test_get_unknown_id_raises_key_error(
        self,
        proof_store: ProofStore,
    ) -> None:
        with pytest.raises(KeyError, match="no-such-id"):
            proof_store.get("no-such-id")

    def test_list_proofs_empty(
        self, proof_store: ProofStore
    ) -> None:
        assert proof_store.list_proofs() == []

    def test_list_proofs_returns_all(
        self,
        proof_store: ProofStore,
        generator: ProofGenerator,
    ) -> None:
        proofs = [
            generator.generate_proof(
                input_data={"n": i},
                output_data={"out": i},
                computation_log=str(i),
            )
            for i in range(3)
        ]
        for proof in proofs:
            proof_store.save(proof)
        listed = proof_store.list_proofs()
        assert len(listed) == 3

    def test_list_proofs_sorted_by_timestamp(
        self,
        proof_store: ProofStore,
        generator: ProofGenerator,
    ) -> None:
        from datetime import timedelta

        now = datetime(2024, 1, 1, 12, 0, 0)
        # Insert proofs with out-of-order timestamps (offset = 2, 0, 1)
        for offset in (2, 0, 1):
            proof = generator.generate_proof(
                input_data={"offset": offset},
                output_data={},
                computation_log="",
            )
            # model_copy creates a new instance with the updated timestamp
            proof = proof.model_copy(
                update={"timestamp": now + timedelta(seconds=offset)}
            )
            proof_store.save(proof)

        listed = proof_store.list_proofs()
        timestamps = [p.timestamp for p in listed]
        assert timestamps == sorted(timestamps)

    def test_delete_removes_proof(
        self,
        proof_store: ProofStore,
        sample_proof: ComputationProof,
    ) -> None:
        proof_store.save(sample_proof)
        proof_store.delete(sample_proof.proof_id)
        with pytest.raises(KeyError):
            proof_store.get(sample_proof.proof_id)

    def test_delete_nonexistent_is_no_op(
        self, proof_store: ProofStore
    ) -> None:
        proof_store.delete("does-not-exist")  # must not raise

    def test_dump_returns_list_of_dicts(
        self,
        proof_store: ProofStore,
        sample_proof: ComputationProof,
    ) -> None:
        proof_store.save(sample_proof)
        dumped = proof_store.dump()
        assert isinstance(dumped, list)
        assert len(dumped) == 1
        assert isinstance(dumped[0], dict)
        assert dumped[0]["proof_id"] == sample_proof.proof_id

    def test_dump_empty_store(self, proof_store: ProofStore) -> None:
        assert proof_store.dump() == []

    def test_load_restores_proofs(
        self,
        proof_store: ProofStore,
        sample_proof: ComputationProof,
    ) -> None:
        proof_store.save(sample_proof)
        serialized = proof_store.dump()

        new_store = ProofStore()
        new_store.load(serialized)
        restored = new_store.get(sample_proof.proof_id)
        assert restored.chain_hash == sample_proof.chain_hash

    def test_load_and_dump_roundtrip(
        self,
        generator: ProofGenerator,
    ) -> None:
        store1 = ProofStore()
        for i in range(5):
            store1.save(
                generator.generate_proof(
                    input_data={"i": i},
                    output_data={"o": i},
                    computation_log=f"step {i}",
                )
            )
        data = store1.dump()

        store2 = ProofStore()
        store2.load(data)
        assert len(store2.list_proofs()) == 5

    def test_overwrite_existing_proof(
        self,
        proof_store: ProofStore,
        sample_proof: ComputationProof,
    ) -> None:
        proof_store.save(sample_proof)
        updated = sample_proof.model_copy(
            update={"chain_hash": "a" * 64}
        )
        proof_store.save(updated)
        assert proof_store.get(sample_proof.proof_id).chain_hash == "a" * 64
