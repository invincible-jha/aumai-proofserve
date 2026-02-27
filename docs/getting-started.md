# Getting Started with aumai-proofserve

This guide walks you from a fresh install to generating and verifying your first cryptographic
computation proof in under ten minutes.

---

## Prerequisites

- Python 3.11 or later
- `pip` (any recent version)
- Basic familiarity with Python dicts and JSON

No external services, cryptographic libraries, or API keys are required.
`aumai-proofserve` uses only Python's built-in `hashlib` (SHA-256) plus Pydantic for model
validation.

---

## What Is a Computation Proof?

A `ComputationProof` is a record of four SHA-256 hashes:

1. `input_hash` — hash of the canonical JSON encoding of the input data
2. `output_hash` — hash of the canonical JSON encoding of the output data
3. `computation_hash` — hash of the computation log text
4. `chain_hash` — hash of the concatenation of the three component hashes

Together, these four values uniquely identify a specific computation. If any part changes —
even a single character — the chain hash will not match, and the proof becomes invalid.

---

## Installation

### From PyPI

```bash
pip install aumai-proofserve
```

### From Source

```bash
git clone https://github.com/aumai/aumai-proofserve.git
cd aumai-proofserve
pip install -e ".[dev]"
```

### Verify

```bash
aumai-proofserve --version
# aumai-proofserve, version 0.1.0

python -c "from aumai_proofserve.core import ProofGenerator; print('OK')"
# OK
```

---

## Step-by-Step Tutorial

### Step 1 — Create a ProofGenerator

The `ProofGenerator` is a stateless object. You can create a new instance for each computation
or share one across your application.

```python
from aumai_proofserve.core import ProofGenerator

generator = ProofGenerator()
```

---

### Step 2 — Define Your Computation

A computation has three components:

- **Input data** — the data that was fed into the computation (a Python dict)
- **Output data** — the result produced (a Python dict)
- **Computation log** — a free-text description of the steps taken (a string)

```python
input_data = {
    "document_id": "INVOICE-2025-0042",
    "field": "total_amount",
    "currency": "USD",
}

output_data = {
    "extracted_value": 14750.00,
    "confidence": 0.99,
    "extraction_method": "structured_parsing",
}

computation_log = (
    "Step 1: Located 'Total' label in bottom-right table cell. "
    "Step 2: Parsed numeric value using regex pattern for USD amounts. "
    "Step 3: Validated against expected range [0, 1000000]."
)
```

---

### Step 3 — Generate the Proof

```python
proof = generator.generate_proof(
    input_data=input_data,
    output_data=output_data,
    computation_log=computation_log,
    metadata={
        "agent_id": "invoice-extractor-v2",
        "model": "gpt-4o",
        "run_id": "run-2025-11-01-001",
    },
)

print(f"Proof ID         : {proof.proof_id}")
print(f"Input hash       : {proof.input_hash}")
print(f"Output hash      : {proof.output_hash}")
print(f"Computation hash : {proof.computation_hash}")
print(f"Chain hash       : {proof.chain_hash}")
print(f"Algorithm        : {proof.algorithm}")
print(f"Timestamp        : {proof.timestamp}")
```

The `metadata` dict is stored in the proof but does not affect any hash values. Use it to
annotate proofs with system identifiers, model versions, run IDs, etc.

---

### Step 4 — Store the Proof

```python
from aumai_proofserve.core import ProofStore

store = ProofStore()
store.save(proof)

print(f"Total proofs in store: {len(store.list_proofs())}")
```

---

### Step 5 — Persist the Store to Disk

```python
import json
from pathlib import Path

# Save
Path("proof_store.json").write_text(
    json.dumps(store.dump(), indent=2), encoding="utf-8"
)

# Restore in a new process or session
new_store = ProofStore()
new_store.load(json.loads(Path("proof_store.json").read_text()))
print(f"Restored {len(new_store.list_proofs())} proof(s).")
```

---

### Step 6 — Verify a Proof

```python
from aumai_proofserve.core import ProofVerifier

verifier = ProofVerifier()

result = verifier.verify(
    proof=proof,
    input_data=input_data,
    output_data=output_data,
    computation_log=computation_log,
)

if result.valid:
    print(f"VALID: {result.details}")
else:
    print(f"INVALID: {result.details}")
```

---

### Step 7 — Test Tamper Detection

Modify one field of the output and verify again:

```python
tampered_output = {
    "extracted_value": 14751.00,  # one dollar off
    "confidence": 0.99,
    "extraction_method": "structured_parsing",
}

tampered_result = verifier.verify(
    proof=proof,
    input_data=input_data,
    output_data=tampered_output,
    computation_log=computation_log,
)

print(f"Valid: {tampered_result.valid}")   # False
print(tampered_result.details)
# Verification failed:
# output_hash mismatch: expected '...' got '...'
# chain_hash mismatch: expected '...' got '...'
```

The verifier reports both the `output_hash` mismatch and the cascading `chain_hash` mismatch,
making it immediately clear which component was altered.

---

### Step 8 — Using the CLI

**Generate a proof from files:**

```bash
echo '{"doc": "INV-42", "field": "total"}' > input.json
echo '{"value": 14750.0, "confidence": 0.99}' > output.json
echo "Parsed total from bottom-right cell." > computation.log

aumai-proofserve prove \
  --input input.json \
  --output output.json \
  --log computation.log \
  --proof-out proof.json \
  --store proof_store.json
```

**Verify a proof:**

```bash
aumai-proofserve verify \
  --proof proof.json \
  --input input.json \
  --output output.json \
  --log computation.log
```

**List all stored proofs:**

```bash
aumai-proofserve list --store proof_store.json
```

---

## Common Patterns and Recipes

### Pattern 1 — Proof as a Post-Processing Step

Generate a proof automatically after every agent task completes:

```python
from aumai_proofserve.core import ProofGenerator, ProofStore

_generator = ProofGenerator()
_store = ProofStore()


def run_agent_task(task_input: dict) -> dict:
    """Run the task and generate a verifiable proof of the computation."""
    # ... your agent logic here ...
    task_output = {"result": "computed_value", "score": 0.87}
    computation_log = f"Processed task with input keys: {list(task_input.keys())}"

    proof = _generator.generate_proof(
        input_data=task_input,
        output_data=task_output,
        computation_log=computation_log,
    )
    _store.save(proof)

    # Return both the output and the proof ID for traceability
    return {**task_output, "proof_id": proof.proof_id}
```

---

### Pattern 2 — Retrieving and Re-Verifying a Proof by ID

```python
from aumai_proofserve.core import ProofStore, ProofVerifier

store = ProofStore()
# ... load from disk ...

verifier = ProofVerifier()

proof_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
proof = store.get(proof_id)  # raises KeyError if not found

result = verifier.verify(
    proof=proof,
    input_data={"doc": "INV-42"},  # must match original exactly
    output_data={"value": 14750.0},
)
print(result.valid)
```

---

### Pattern 3 — Integrating with aumai-transparency

Use an audit trail as the `computation_log` to bind the trail to the proof:

```python
from aumai_transparency.core import AuditLogger
from aumai_proofserve.core import ProofGenerator

audit_logger = AuditLogger()
# ... log events ...

trail = audit_logger.get_trail("my-agent")
trail_json = audit_logger.export_trail(trail, fmt="json")  # deterministic JSON

generator = ProofGenerator()
proof = generator.generate_proof(
    input_data={"agent_id": "my-agent", "task": "classify"},
    output_data={"label": "urgent", "confidence": 0.96},
    computation_log=trail_json,  # the full audit trail becomes the log
    metadata={"trail_id": trail.trail_id},
)
```

Now the proof cryptographically commits to the full audit trail. Any retroactive modification
to the trail will invalidate the chain hash.

---

### Pattern 4 — Listing and Auditing All Proofs

```python
from aumai_proofserve.core import ProofStore
from datetime import datetime, timezone

store = ProofStore()
# ... load from disk ...

proofs = store.list_proofs()  # sorted by timestamp ascending
print(f"Total proofs: {len(proofs)}")

for proof in proofs:
    age_seconds = (
        datetime.now(tz=timezone.utc) - proof.timestamp
    ).total_seconds()
    print(
        f"{proof.proof_id[:8]}... | "
        f"{proof.timestamp.isoformat()[:19]} | "
        f"age={age_seconds:.0f}s | "
        f"chain={proof.chain_hash[:16]}..."
    )
```

---

### Pattern 5 — Proof Deletion for Privacy Compliance

If a proof must be deleted (e.g., GDPR right-to-erasure for metadata containing personal data):

```python
from aumai_proofserve.core import ProofStore

store = ProofStore()
# ... load from disk ...

proof_id_to_delete = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
store.delete(proof_id_to_delete)  # no-op if ID does not exist

# Persist the updated store
import json
from pathlib import Path
Path("proof_store.json").write_text(json.dumps(store.dump(), indent=2))
```

Note: Deleting a proof removes the hash record, but the hashes themselves cannot "unprove"
a computation — anyone with the original inputs and outputs can recompute and verify them.

---

## Troubleshooting FAQ

**Q: `verify()` returns `valid=False` even though I haven't changed anything.**

The most common cause is key ordering in your dict literals. If your `input_data` at
verification time has a different key order than at proof generation time, the canonical JSON
will be identical (keys are sorted), so this should not cause a mismatch. However, if a value
contains a floating-point number, `1.0` and `1` are different JSON representations. Ensure
you are passing exactly the same Python values at both proof generation and verification.

---

**Q: `store.get(proof_id)` raises `KeyError`.**

The store is in-memory only. If you created a `ProofStore`, saved a proof, and then created
a new `ProofStore` in a different code path or process, the second instance starts empty.
Load from disk first using `store.load(json.loads(Path("proof_store.json").read_text()))`.

---

**Q: The `computation_log` is optional but I want to include it — what format should I use?**

Any UTF-8 string is valid. Common formats: plain text step descriptions, JSON-serialized audit
trails (from `aumai-transparency`), or structured log output. Whatever you pass at proof
generation time must be passed identically at verification time, including whitespace and line
endings.

---

**Q: Can I use `aumai-proofserve` for binary data (images, PDFs)?**

The current API only supports `dict` input/output (JSON-serializable) and string computation
logs. For binary data, compute a SHA-256 hash of the binary content yourself and include that
hash string as a value in the input/output dict. This preserves the proof structure while
covering binary artifacts.

---

**Q: How do I verify a proof without the computation log?**

Pass `computation_log=""` (the default). The `computation_hash` comparison is skipped when
`computation_log` is empty, but `input_hash`, `output_hash`, and `chain_hash` are still checked.
Note: this means a proof generated with a non-empty log will fail verification if you pass
`computation_log=""` and the original `computation_hash` was non-trivial.

---

**Q: Is SHA-256 secure enough for this use case?**

SHA-256 provides 128 bits of collision resistance. For offline audit trails (non-adversarial
environments where you control all data inputs), it is more than sufficient. For adversarial
environments where an attacker might craft colliding inputs, consult a cryptographer about
upgrading to SHA-3 or adding a HMAC with a secret key.
