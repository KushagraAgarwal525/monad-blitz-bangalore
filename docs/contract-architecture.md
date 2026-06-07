# Contract Architecture

## Deploy Order

1. MemoryToken (MEM)
2. MemoryRegistry
3. RoyaltyEngine
4. LicenseManager
5. MemoryScoreRegistry

## PaymentType

```solidity
enum PaymentType { MEM, MON }  // MVP: MEM only
```

## MemoryRegistry

- `verifyLineage()` — structural only
- `createCommit()` — MVP rejects merge (`parentCount != 1`)
- Fork: `msg.sender` owns child repository

## Events

- RepositoryRegistered, CommitRecorded, RepositoryForked
- LicensePurchased, RevenueRecorded, RoyaltyDistributed
- ScoreSnapshotRecorded

## Structural Provenance Verification

Gas-bounded view function. No hash recomputation.

## Cryptographic Content Verification

Backend responsibility — see canonical-hashing.md

## Future Merge Commit Compatibility

`secondaryParents` mapping + `parentCount` in commit struct.
