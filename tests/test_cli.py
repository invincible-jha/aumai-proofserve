"""Tests for aumai_proofserve CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from aumai_proofserve.cli import main
from aumai_proofserve.core import ProofGenerator
from aumai_proofserve.models import ComputationProof


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


class TestVersionFlag:
    def test_version_exits_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# prove command
# ---------------------------------------------------------------------------


class TestProveCommand:
    def test_prove_generates_proof_file(self, tmp_path: Path) -> None:
        inp = _write_json(tmp_path / "in.json", {"q": "hello"})
        out = _write_json(tmp_path / "out.json", {"a": "world"})
        proof_out = str(tmp_path / "proof.json")
        store_path = str(tmp_path / "store.json")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "prove",
                "--input", str(inp),
                "--output", str(out),
                "--proof-out", proof_out,
                "--store", store_path,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Proof generated:" in result.output
        assert "chain_hash" in result.output
        assert Path(proof_out).exists()

    def test_prove_writes_valid_proof_json(self, tmp_path: Path) -> None:
        inp = _write_json(tmp_path / "in.json", {"data": [1, 2, 3]})
        out = _write_json(tmp_path / "out.json", {"result": 6})
        proof_out = str(tmp_path / "proof.json")
        store_path = str(tmp_path / "store.json")

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "prove",
                "--input", str(inp),
                "--output", str(out),
                "--proof-out", proof_out,
                "--store", store_path,
            ],
        )
        proof_data = json.loads(Path(proof_out).read_text())
        proof = ComputationProof.model_validate(proof_data)
        assert len(proof.input_hash) == 64
        assert len(proof.chain_hash) == 64

    def test_prove_with_log_file(self, tmp_path: Path) -> None:
        inp = _write_json(tmp_path / "in.json", {"x": 1})
        out = _write_json(tmp_path / "out.json", {"y": 2})
        log = tmp_path / "log.txt"
        log.write_text("step 1\nstep 2", encoding="utf-8")
        proof_out = str(tmp_path / "proof.json")
        store_path = str(tmp_path / "store.json")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "prove",
                "--input", str(inp),
                "--output", str(out),
                "--log", str(log),
                "--proof-out", proof_out,
                "--store", store_path,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "computation_hash" in result.output

    def test_prove_writes_to_store(self, tmp_path: Path) -> None:
        inp = _write_json(tmp_path / "in.json", {"val": 42})
        out = _write_json(tmp_path / "out.json", {"val": 42})
        proof_out = str(tmp_path / "p.json")
        store_path = str(tmp_path / "store.json")

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "prove",
                "--input", str(inp),
                "--output", str(out),
                "--proof-out", proof_out,
                "--store", store_path,
            ],
        )
        store_data = json.loads(Path(store_path).read_text())
        assert len(store_data) == 1

    def test_prove_missing_input_option_fails(self, tmp_path: Path) -> None:
        out = _write_json(tmp_path / "out.json", {})
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["prove", "--output", str(out), "--proof-out", "p.json"],
        )
        assert result.exit_code != 0

    def test_prove_accumulates_in_store(self, tmp_path: Path) -> None:
        store_path = str(tmp_path / "store.json")
        runner = CliRunner()
        for i in range(3):
            inp = _write_json(tmp_path / f"in{i}.json", {"n": i})
            out = _write_json(tmp_path / f"out{i}.json", {"n": i})
            runner.invoke(
                main,
                [
                    "prove",
                    "--input", str(inp),
                    "--output", str(out),
                    "--proof-out", str(tmp_path / f"proof{i}.json"),
                    "--store", store_path,
                ],
            )
        store_data = json.loads(Path(store_path).read_text())
        assert len(store_data) == 3


# ---------------------------------------------------------------------------
# verify command
# ---------------------------------------------------------------------------


class TestVerifyCommand:
    def _build_proof_fixture(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path]:
        input_data = {"query": "test"}
        output_data = {"answer": "42"}
        inp = _write_json(tmp_path / "in.json", input_data)
        out = _write_json(tmp_path / "out.json", output_data)

        gen = ProofGenerator()
        proof = gen.generate_proof(
            input_data=input_data,
            output_data=output_data,
            computation_log="",
        )
        proof_file = tmp_path / "proof.json"
        proof_file.write_text(proof.model_dump_json(), encoding="utf-8")
        return inp, out, proof_file

    def test_verify_valid_proof_exits_zero(self, tmp_path: Path) -> None:
        inp, out, proof_file = self._build_proof_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "verify",
                "--proof", str(proof_file),
                "--input", str(inp),
                "--output", str(out),
            ],
        )
        assert result.exit_code == 0
        assert "VALID" in result.output

    def test_verify_tampered_input_exits_nonzero(
        self, tmp_path: Path
    ) -> None:
        _, out, proof_file = self._build_proof_fixture(tmp_path)
        tampered_inp = _write_json(tmp_path / "tampered.json", {"evil": True})
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "verify",
                "--proof", str(proof_file),
                "--input", str(tampered_inp),
                "--output", str(out),
            ],
        )
        assert result.exit_code != 0

    def test_verify_with_log(self, tmp_path: Path) -> None:
        input_data = {"q": "hi"}
        output_data = {"a": "hello"}
        computation_log = "step 1\nstep 2"

        inp = _write_json(tmp_path / "in.json", input_data)
        out = _write_json(tmp_path / "out.json", output_data)
        log = tmp_path / "log.txt"
        log.write_text(computation_log, encoding="utf-8")

        gen = ProofGenerator()
        proof = gen.generate_proof(
            input_data=input_data,
            output_data=output_data,
            computation_log=computation_log,
        )
        proof_file = tmp_path / "proof.json"
        proof_file.write_text(proof.model_dump_json(), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "verify",
                "--proof", str(proof_file),
                "--input", str(inp),
                "--output", str(out),
                "--log", str(log),
            ],
        )
        assert result.exit_code == 0

    def test_verify_missing_proof_option_fails(
        self, tmp_path: Path
    ) -> None:
        inp = _write_json(tmp_path / "in.json", {})
        out = _write_json(tmp_path / "out.json", {})
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["verify", "--input", str(inp), "--output", str(out)],
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# list command
# ---------------------------------------------------------------------------


class TestListCommand:
    def test_list_empty_store_prints_no_proofs(
        self, tmp_path: Path
    ) -> None:
        store_path = str(tmp_path / "store.json")
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["list", "--store", store_path],
        )
        assert result.exit_code == 0
        assert "No proofs found" in result.output

    def test_list_shows_stored_proofs(self, tmp_path: Path) -> None:
        # First prove, then list
        inp = _write_json(tmp_path / "in.json", {"x": 1})
        out = _write_json(tmp_path / "out.json", {"y": 1})
        store_path = str(tmp_path / "store.json")
        proof_out = str(tmp_path / "p.json")

        runner = CliRunner()
        runner.invoke(
            main,
            [
                "prove",
                "--input", str(inp),
                "--output", str(out),
                "--proof-out", proof_out,
                "--store", store_path,
            ],
        )
        result = runner.invoke(
            main, ["list", "--store", store_path]
        )
        assert result.exit_code == 0
        assert "chain=" in result.output

    def test_list_multiple_proofs(self, tmp_path: Path) -> None:
        store_path = str(tmp_path / "store.json")
        runner = CliRunner()
        for i in range(3):
            inp = _write_json(tmp_path / f"in{i}.json", {"n": i})
            out = _write_json(tmp_path / f"out{i}.json", {})
            runner.invoke(
                main,
                [
                    "prove",
                    "--input", str(inp),
                    "--output", str(out),
                    "--proof-out", str(tmp_path / f"p{i}.json"),
                    "--store", store_path,
                ],
            )
        result = runner.invoke(main, ["list", "--store", store_path])
        assert result.exit_code == 0
        lines = [ln for ln in result.output.splitlines() if "chain=" in ln]
        assert len(lines) == 3
