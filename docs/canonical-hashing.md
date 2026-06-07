# Canonical Hashing Specification

Normative protocol spec for cross-service hash compatibility.

## Content Canonicalization

```python
canonical = json.dumps(content_obj, sort_keys=True, separators=(",", ":"))
content_hash = keccak256(canonical.encode("utf-8"))
```

## Embedding Serialization

```python
embedding_bytes = np.asarray(embedding, dtype=np.float32).tobytes()
embedding_hash = keccak256(embedding_bytes)
```

## stateRoot

```
keccak256(content_hash || embedding_hash || primary_parent || source_attribution_hash || author || timestamp)
```

## commit_hash (single formula — MVP and future)

```
secondary_parents_canonical = bytes32(0)  # MVP
commit_hash = keccak256(state_root || primary_parent || secondary_parents_canonical || creator || timestamp)
```

Future merge: `secondary_parents_canonical = keccak256(sorted secondary parent hashes)`.

## Structural Provenance Verification

See architecture.md — on-chain structural checks only.

## Cryptographic Content Verification

Backend recomputes all hashes and compares to stored commitments.

## Future Merge Commit Compatibility

MVP commits use `parentCount=1` and `secondary_parents_canonical=0x0`. No schema migration required for merge support.

## Golden Vector (MVP)

```
content: {"text":"hello","format":"markdown"}
secondary_parents_canonical: 0x000...000
→ commit_hash stable across Python backend and integrators
```
