"""CLI entry point for aumai-proofserve."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from .core import ProofGenerator, ProofStore, ProofVerifier
from .models import ComputationProof


@click.group()
@click.version_option()
def main() -> None:
    """AumAI ProofServe — verifiable computation for agent outputs."""


@main.command("prove")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="JSON file containing the computation input.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="JSON file containing the computation output.",
)
@click.option(
    "--log",
    "log_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Optional text file containing the computation log.",
)
@click.option(
    "--proof-out",
    "proof_out_path",
    default="proof.json",
    show_default=True,
    help="Path to write the generated proof JSON.",
)
@click.option(
    "--store",
    "store_path",
    default="proof_store.json",
    show_default=True,
    help="Path to the persistent proof store.",
)
def prove_command(
    input_path: str,
    output_path: str,
    log_path: str | None,
    proof_out_path: str,
    store_path: str,
) -> None:
    """Generate a verifiable proof for a computation."""
    input_data = json.loads(Path(input_path).read_text())
    output_data = json.loads(Path(output_path).read_text())
    computation_log = (
        Path(log_path).read_text() if log_path else ""
    )

    generator = ProofGenerator()
    proof = generator.generate_proof(
        input_data=input_data,
        output_data=output_data,
        computation_log=computation_log,
        metadata={"input_file": input_path, "output_file": output_path},
    )

    # Save proof JSON
    Path(proof_out_path).write_text(
        proof.model_dump_json(indent=2), encoding="utf-8"
    )

    # Persist to store
    store = ProofStore()
    _load_proof_store(store, store_path)
    store.save(proof)
    _save_proof_store(store, store_path)

    click.echo(f"Proof generated: {proof.proof_id}")
    click.echo(f"  input_hash      : {proof.input_hash}")
    click.echo(f"  output_hash     : {proof.output_hash}")
    click.echo(f"  computation_hash: {proof.computation_hash}")
    click.echo(f"  chain_hash      : {proof.chain_hash}")
    click.echo(f"  Written to      : {proof_out_path}")


@main.command("verify")
@click.option(
    "--proof",
    "proof_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="JSON file containing the proof.",
)
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="JSON file containing the original input.",
)
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="JSON file containing the original output.",
)
@click.option(
    "--log",
    "log_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Optional computation log file.",
)
def verify_command(
    proof_path: str,
    input_path: str,
    output_path: str,
    log_path: str | None,
) -> None:
    """Verify a proof against original input/output data."""
    proof = ComputationProof.model_validate(
        json.loads(Path(proof_path).read_text())
    )
    input_data = json.loads(Path(input_path).read_text())
    output_data = json.loads(Path(output_path).read_text())
    computation_log = (
        Path(log_path).read_text() if log_path else ""
    )

    verifier = ProofVerifier()
    result = verifier.verify(
        proof=proof,
        input_data=input_data,
        output_data=output_data,
        computation_log=computation_log,
    )

    if result.valid:
        click.echo(f"VALID   Proof {proof.proof_id}")
        click.echo(f"        {result.details}")
    else:
        click.echo(f"INVALID Proof {proof.proof_id}", err=True)
        click.echo(result.details, err=True)
        sys.exit(1)


@main.command("list")
@click.option(
    "--store", "store_path", default="proof_store.json", show_default=True
)
def list_command(store_path: str) -> None:
    """List all proofs in the store."""
    store = ProofStore()
    _load_proof_store(store, store_path)
    proofs = store.list_proofs()
    if not proofs:
        click.echo("No proofs found.")
        return
    for proof in proofs:
        click.echo(
            f"{proof.proof_id}  {proof.timestamp.isoformat()[:19]}  "
            f"chain={proof.chain_hash[:16]}..."
        )


def _load_proof_store(store: ProofStore, path: str) -> None:
    p = Path(path)
    if p.exists():
        store.load(json.loads(p.read_text()))


def _save_proof_store(store: ProofStore, path: str) -> None:
    Path(path).write_text(json.dumps(store.dump(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
