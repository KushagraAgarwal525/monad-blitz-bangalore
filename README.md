# Memoria

> **Cognition lives off-chain. Ownership lives on Monad.**

Memoria is an ownership and provenance protocol for AI memory — not an on-chain vector database.

## Quick Start

```bash
cp .env.example .env
docker-compose up -d postgres qdrant
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd web && npm install && npm run dev
```

### Contracts (requires Foundry)

Run these from the `contracts/` directory (not the repo root). In **Git Bash**: `cd /c/Users/<you>/MemoryOS/contracts`. In **WSL**: `cd /mnt/c/Users/<you>/MemoryOS/contracts`.

```bash
cd contracts
forge install --no-git foundry-rs/forge-std
forge install --no-git OpenZeppelin/openzeppelin-contracts
forge test
forge script script/Deploy.s.sol --rpc-url https://testnet-rpc.monad.xyz --broadcast
```

### Demo seed

```bash
python scripts/seed_demo.py
bash scripts/demo.sh
```

## Architecture

- **On-chain:** ownership, commits, forks, licenses, royalties, structural `verifyLineage()`
- **Off-chain:** Qdrant vectors, Fireworks LLM, cryptographic provenance verification
- **Payments:** MemoryToken (MEM)

See [docs/architecture.md](docs/architecture.md), [docs/canonical-hashing.md](docs/canonical-hashing.md).

## Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard |
| `/marketplace` | Browse repos + Knowledge Revenue |
| `/repositories/[id]` | Commits, Lineage DAG, Provenance |
| `/agent` | Research agent (propose → approve → commit) |
| `/analytics` | Royalty analytics |

## License

MIT
