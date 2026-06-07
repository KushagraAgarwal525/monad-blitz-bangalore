# Memoria Architecture

> Cognition lives off-chain. Ownership lives on Monad.

Memoria is **not** an on-chain vector database. It is an ownership and provenance protocol for AI memory.

## Git Analogy

| Git | Memoria |
|-----|---------|
| Repository | Memory Repository |
| Commit | MemoryCommit |
| Fork | New repository from fork point |
| Lineage | Commit DAG + fork chain |

## Structural Provenance Verification

On-chain `verifyLineage()` checks:
- Repository ancestry (D → C → B → A)
- Fork link validity
- Commit parent chain
- Commit existence

**Does not** recompute content hashes on-chain.

## Cryptographic Content Verification

Backend `GET /repositories/{id}/provenance/verify`:
1. Re-fetch Qdrant content
2. Recompute hashes per canonical-hashing.md
3. Compare to on-chain commitments

## Future Merge Commit Compatibility

- `parentCount == 1` → normal commit (MVP)
- `parentCount > 1` → merge commit (future)
- `commit_hash` always includes `secondary_parents_canonical` (`bytes32(0)` in MVP)

## HEAD Semantics (MVP)

Linear history only. `headCommitHash` = active tip. Future merge-enabled repos may have non-linear graphs.

## Agent Flow

Propose → User approves → Commit recorded. No autonomous persistence.
