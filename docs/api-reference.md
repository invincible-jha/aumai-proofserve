# API Reference — aumai-proofserve

Complete reference for all public classes, methods, and Pydantic models.

Source modules:
- `aumai_proofserve.core` — `ProofGenerator`, `ProofVerifier`, `ProofStore`
- `aumai_proofserve.models` — `ComputationProof`, `VerificationResult`
- `aumai_proofserve.cli` — CLI entry point (`aumai-proofserve`)

---

## Module: `aumai_proofserve.core`

### class `ProofGenerator`

Generates SHA-256 hash-chain proofs for agent computations.

Stateless: a single instance can generate proofs for any number of computations. All state
lives in the returned `ComputationProof` objects.

```python
from aumai_proofserve.core import ProofGenerator

generator = ProofGenerator()
```

The proof construction algorithm is:

```
input_hash       = SHA-256( canonical_json(input_data) )
output_hash      = SHA-256( canonical_json(output_data) )
computation_hash = SHA-256( computation_log.encode("utf-8") )
chain_hash       = SHA-256( (input_hash + output_hash + computation_hash).encode("ascii") )
```

where `canonical_json(data)` = `json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")`.

---

#### `ProofGenerator.generate_proof()`

```python
def generate_proof(
    self,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    computation_log: str,
    metadata: dict[str, Any] | None = None,
) -> ComputationProof:
```

Generate a verifiable proof for a computation.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `input_data` | `dict[str, Any]` | The input payload. Must be JSON-serializable. Keys are sorted before hashing. |
| `output_data` | `dict[str, Any]` | The output payload. Must be JSON-serializable. Keys are sorted before hashing. |
| `computation_log` | `str` | Free-text description of computation steps. Pass `""` if no log exists. |
| `metadata` | `dict[str, Any] \| None` | Optional key-value annotations stored in the proof. Do not affect any hash. Defaults to `{}`. |

**Returns:** `ComputationProof` with a fresh UUID `proof_id`, four SHA-256 hashes, UTC timestamp,
and the provided metadata.

**Note on JSON-serializability:** Values that are not JSON-serializable by default (e.g.
`datetime` objects) will raise `TypeError` from `json.dumps`. Pre-convert such values to strings
before passing them to `generate_proof()`.

**Example:**

```python
proof = generator.generate_proof(
    input_data={
        "contract_id": "C-4421",
        "clause_index": 7,
        "text": "The vendor warrants...",
    },
    output_data={
        "risk_level": "medium",
        "score": 0.54,
        "flags": ["warranty", "indemnification"],
    },
    computation_log=(
        "Step 1: Tokenized clause text. "
        "Step 2: Ran risk classifier v3.1. "
        "Step 3: Score 0.54 exceeds medium-risk threshold of 0.50."
    ),
    metadata={
        "agent_id": "risk-classifier-01",
        "model_version": "v3.1",
        "run_id": "run-2025-11-01-042",
    },
)

print(proof.proof_id)    # UUID string
print(proof.chain_hash)  # 64-char hex string
print(proof.algorithm)   # "sha256"
```

---

### class `ProofVerifier`

Verifies that a `ComputationProof` is consistent with the original input, output, and
computation log.

Stateless: no initialization required. Creates no side effects.

```python
from aumai_proofserve.core import ProofVerifier

verifier = ProofVerifier()
```

---

#### `ProofVerifier.verify()`

```python
def verify(
    self,
    proof: ComputationProof,
    input_data: dict[str, Any],
    output_data: dict[str, Any],
    computation_log: str = "",
) -> VerificationResult:
```

Recompute all four expected hashes from the provided data and compare them against the stored
proof hashes. Returns `VerificationResult(valid=True)` only when all checked hashes match
exactly.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `proof` | `ComputationProof` | The stored proof to verify against. |
| `input_data` | `dict[str, Any]` | The claimed original input data. |
| `output_data` | `dict[str, Any]` | The claimed original output data. |
| `computation_log` | `str` | The claimed original computation log. Defaults to `""`. If empty, the `computation_hash` comparison is skipped. |

**Returns:** `VerificationResult`

- `valid=True` — all checked hashes matched.
- `valid=False` — one or more hashes did not match. `details` contains a failure message
  listing every mismatch, including both the expected and actual hash values.

**Computation log skip behavior:** When `computation_log=""` (the default), the verifier skips
the `computation_hash` comparison. The `input_hash`, `output_hash`, and `chain_hash` are still
verified. This is intentional: a proof generated with a non-empty log will show a `chain_hash`
mismatch when verified with `computation_log=""`, because the expected chain hash is recomputed
using the empty-log `computation_hash`.

**Example — successful verification:**

```python
result = verifier.verify(
    proof=proof,
    input_data={"contract_id": "C-4421", "clause_index": 7, "text": "The vendor warrants..."},
    output_data={"risk_level": "medium", "score": 0.54, "flags": ["warranty", "indemnification"]},
    computation_log=(
        "Step 1: Tokenized clause text. "
        "Step 2: Ran risk classifier v3.1. "
        "Step 3: Score 0.54 exceeds medium-risk threshold of 0.50."
    ),
)
print(result.valid)    # True
print(result.details)  # "All hashes verified successfully."
```

**Example — tampered output:**

```python
tampered_result = verifier.verify(
    proof=proof,
    input_data={"contract_id": "C-4421", "clause_index": 7, "text": "The vendor warrants..."},
    output_data={"risk_level": "low", "score": 0.22, "flags": []},  # altered
    computation_log="...",
)
print(tampered_result.valid)    # False
print(tampered_result.details)
# Verification failed:
# output_hash mismatch: expected 'abc123...' got 'def456...'
# chain_hash mismatch: expected 'ghi789...' got 'jkl012...'
```

---

### class `ProofStore`

In-memory store for `ComputationProof` objects. Provides CRUD operations and full
serialization round-trips.

```python
from aumai_proofserve.core import ProofStore

store = ProofStore()
```

The internal structure is a `dict[str, ComputationProof]` keyed by `proof_id`.

---

#### `ProofStore.save()`

```python
def save(self, proof: ComputationProof) -> None:
```

Store a proof by its `proof_id`. Overwrites any existing proof with the same ID.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `proof` | `ComputationProof` | The proof to store. |

**Example:**

```python
proof = generator.generate_proof(...)
store.save(proof)
```

---

#### `ProofStore.get()`

```python
def get(self, proof_id: str) -> ComputationProof:
```

Retrieve a proof by its `proof_id`.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `proof_id` | `str` | The UUID string of the proof to retrieve. |

**Returns:** `ComputationProof`

**Raises:** `KeyError` with message `"No proof found with id '{proof_id}'."` if the ID does not
exist in the store.

**Example:**

```python
try:
    proof = store.get("3fa85f64-5717-4562-b3fc-2c963f66afa6")
except KeyError as exc:
    print(f"Not found: {exc}")
```

---

#### `ProofStore.list_proofs()`

```python
def list_proofs(self) -> list[ComputationProof]:
```

Return all stored proofs ordered by `timestamp` ascending (oldest first).

**Returns:** `list[ComputationProof]` — sorted by `proof.timestamp`.

**Example:**

```python
for proof in store.list_proofs():
    print(f"{proof.proof_id} | {proof.timestamp.isoformat()[:19]} | chain={proof.chain_hash[:16]}...")
```

---

#### `ProofStore.delete()`

```python
def delete(self, proof_id: str) -> None:
```

Remove a proof from the store. No-op if `proof_id` does not exist.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `proof_id` | `str` | The UUID of the proof to delete. |

**Example:**

```python
store.delete("3fa85f64-5717-4562-b3fc-2c963f66afa6")
```

---

#### `ProofStore.dump()`

```python
def dump(self) -> list[dict[str, Any]]:
```

Serialize all stored proofs to a list of plain dicts (via `ComputationProof.model_dump(mode="json")`).

**Returns:** `list[dict[str, Any]]` — suitable for `json.dumps()` and database storage.

**Example:**

```python
import json
from pathlib import Path

data = store.dump()
Path("proof_store.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
```

---

#### `ProofStore.load()`

```python
def load(self, data: list[dict[str, Any]]) -> None:
```

Restore proofs from a list of serialized dicts (as produced by `dump()`). Adds to any
existing proofs in the store; does not clear first. Call on a fresh `ProofStore()` to restore
a clean state.

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | `list[dict[str, Any]]` | List of serialized proof dicts. |

**Raises:** `pydantic.ValidationError` if any dict does not conform to the `ComputationProof`
schema.

**Example:**

```python
import json
from pathlib import Path

store = ProofStore()
raw = json.loads(Path("proof_store.json").read_text())
store.load(raw)
print(f"Loaded {len(store.list_proofs())} proof(s).")
```

---

## Module: `aumai_proofserve.models`

All models are Pydantic v2 `BaseModel` subclasses. Serialize any model with `.model_dump()` or
`.model_dump_json()`.

---

### class `ComputationProof`

Cryptographic proof of a computation's inputs, outputs, and steps.

```python
from aumai_proofserve.models import ComputationProof
```

**Fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `proof_id` | `str` | required | UUID string assigned at proof generation time. |
| `input_hash` | `str` | required | Lowercase hex SHA-256 digest of `canonical_json(input_data)`. |
| `output_hash` | `str` | required | Lowercase hex SHA-256 digest of `canonical_json(output_data)`. |
| `computation_hash` | `str` | required | Lowercase hex SHA-256 digest of `computation_log.encode("utf-8")`. |
| `chain_hash` | `str` | required | Lowercase hex SHA-256 of `(input_hash + output_hash + computation_hash).encode("ascii")`. |
| `algorithm` | `str` | `"sha256"` | Hashing algorithm identifier. Currently always `"sha256"`. |
| `timestamp` | `datetime` | `datetime.now(UTC)` | UTC timestamp when the proof was generated. |
| `metadata` | `dict[str, Any]` | `{}` | Arbitrary annotations. Do not affect any hash value. |

**Note:** All four hash fields are 64-character lowercase hexadecimal strings representing
256-bit SHA-256 digests.

**Serialization example:**

```python
proof = generator.generate_proof(...)

# To JSON string
json_str = proof.model_dump_json(indent=2)

# To dict
d = proof.model_dump(mode="json")

# Reconstruct from dict
from aumai_proofserve.models import ComputationProof
proof2 = ComputationProof.model_validate(d)
```

---

### class `VerificationResult`

Result of verifying a `ComputationProof` against input/output data.

```python
from aumai_proofserve.models import VerificationResult
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `valid` | `bool` | `True` if all checked hashes matched; `False` otherwise. |
| `proof` | `ComputationProof` | The proof that was verified (reference to the original object). |
| `details` | `str` | Human-readable result. `"All hashes verified successfully."` on success; a multi-line failure message listing every hash mismatch on failure. |

**Failure message format:**

```
Verification failed:
input_hash mismatch: expected '{expected}', got '{actual}'
output_hash mismatch: expected '{expected}', got '{actual}'
computation_hash mismatch: expected '{expected}', got '{actual}'
chain_hash mismatch: expected '{expected}', got '{actual}'
```

Only mismatches that actually occurred are included. A single tampered field typically causes
two mismatches: the field's own hash and the `chain_hash`.

**Example:**

```python
result = verifier.verify(proof=proof, input_data={...}, output_data={...})

if result.valid:
    print(f"Proof {result.proof.proof_id} is valid.")
else:
    print(f"Proof {result.proof.proof_id} is INVALID.")
    print(result.details)
```

---

## Module: `aumai_proofserve.cli`

The CLI is installed as the `aumai-proofserve` command.

### `aumai-proofserve prove`

Generate a verifiable proof from JSON files.

```bash
aumai-proofserve prove \
  --input INPUT_JSON \
  --output OUTPUT_JSON \
  [--log LOG_FILE] \
  [--proof-out PROOF_JSON] \
  [--store STORE_JSON]
```

| Flag | Default | Required | Description |
|------|---------|----------|-------------|
| `--input` | — | yes | JSON file with the computation input. |
| `--output` | — | yes | JSON file with the computation output. |
| `--log` | None | no | Text file with the computation log. |
| `--proof-out` | `proof.json` | no | File to write the generated proof JSON. |
| `--store` | `proof_store.json` | no | Persistent proof store file; proof is appended. |

Prints the proof ID and all four hash values to stdout.

---

### `aumai-proofserve verify`

Verify a proof against the original data files.

```bash
aumai-proofserve verify \
  --proof PROOF_JSON \
  --input INPUT_JSON \
  --output OUTPUT_JSON \
  [--log LOG_FILE]
```

| Flag | Default | Required | Description |
|------|---------|----------|-------------|
| `--proof` | — | yes | JSON file containing the proof. |
| `--input` | — | yes | JSON file containing the original input. |
| `--output` | — | yes | JSON file containing the original output. |
| `--log` | None | no | Text file containing the original computation log. |

Exits with code `0` on success. Exits with code `1` and prints failure details to stderr on
invalid proof.

---

### `aumai-proofserve list`

List all proofs in a proof store file.

```bash
aumai-proofserve list [--store STORE_JSON]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--store` | `proof_store.json` | Path to the proof store file. |

Prints one line per proof: `{proof_id}  {timestamp[:19]}  chain={chain_hash[:16]}...`

---

## Internal Helper Functions

These functions are not exported but are part of the computation contract and documented here
for auditors reproducing the algorithm independently.

### `_canonical_json(data)`

```python
def _canonical_json(data: dict[str, Any]) -> bytes:
```

Produce a deterministic JSON byte-string for `data`. Uses `json.dumps(data, sort_keys=True,
ensure_ascii=False)` encoded to UTF-8. This ensures that dicts with the same key-value pairs
in any insertion order produce identical byte sequences.

### `_sha256(data)`

```python
def _sha256(data: bytes) -> str:
```

Return the lowercase hex SHA-256 digest of `data`. Equivalent to:
`hashlib.sha256(data).hexdigest()`

---

## Exceptions

| Exception | When Raised |
|-----------|-------------|
| `KeyError` | `ProofStore.get()` called with an unknown `proof_id`. |
| `pydantic.ValidationError` | `ProofStore.load()` receives malformed proof dicts. |
| `json.JSONDecodeError` | CLI commands receive non-JSON input files. |
| `TypeError` | `ProofGenerator.generate_proof()` receives a non-JSON-serializable value in `input_data` or `output_data`. |

---

## Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `_ALGORITHM` | `"sha256"` | Hashing algorithm used for all proofs. Set on `ComputationProof.algorithm`. |
