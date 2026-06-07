import json
from typing import Any

import numpy as np
from eth_utils import keccak


def canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def keccak256(data: bytes) -> bytes:
    return keccak(data)


def keccak256_hex(data: bytes) -> str:
    return "0x" + keccak256(data).hex()


def content_hash(content: dict[str, Any]) -> str:
    return keccak256_hex(canonical_json(content).encode("utf-8"))


def source_attribution_hash(source_attribution: dict[str, Any]) -> str:
    return keccak256_hex(canonical_json(source_attribution).encode("utf-8"))


def embedding_hash(embedding: list[float]) -> str:
    arr = np.asarray(embedding, dtype=np.float32)
    return keccak256_hex(arr.tobytes())


def secondary_parents_canonical(secondary_parents: list[str]) -> str:
    if not secondary_parents:
        return "0x" + "00" * 32
    sorted_parents = sorted(secondary_parents)
    packed = b"".join(bytes.fromhex(p[2:] if p.startswith("0x") else p) for p in sorted_parents)
    return keccak256_hex(packed)


def solidity_pack(*parts: bytes) -> bytes:
    return b"".join(parts)


def address_to_bytes20(addr: str) -> bytes:
    h = addr[2:] if addr.startswith("0x") else addr
    return bytes.fromhex(h.zfill(40))


def hex_to_bytes32(h: str) -> bytes:
    raw = h[2:] if h.startswith("0x") else h
    return bytes.fromhex(raw.zfill(64))


def compute_state_root(
    content_h: str,
    embedding_h: str,
    primary_parent: str,
    source_attr_h: str,
    author: str,
    timestamp: int,
) -> str:
    packed = solidity_pack(
        hex_to_bytes32(content_h),
        hex_to_bytes32(embedding_h),
        hex_to_bytes32(primary_parent),
        hex_to_bytes32(source_attr_h),
        address_to_bytes20(author),
        timestamp.to_bytes(32, "big"),
    )
    return keccak256_hex(packed)


def compute_commit_hash(
    state_root: str,
    primary_parent: str,
    secondary_parents_canonical_h: str,
    creator: str,
    timestamp: int,
) -> str:
    packed = solidity_pack(
        hex_to_bytes32(state_root),
        hex_to_bytes32(primary_parent),
        hex_to_bytes32(secondary_parents_canonical_h),
        address_to_bytes20(creator),
        timestamp.to_bytes(32, "big"),
    )
    return keccak256_hex(packed)


def compute_commit_payload(
    content: dict[str, Any],
    embedding: list[float],
    source_attribution: dict[str, Any],
    primary_parent_commit_hash: str,
    secondary_parents: list[str],
    creator: str,
    timestamp: int,
) -> dict[str, str | int]:
    if secondary_parents:
        raise ValueError("Merge commits not supported in MVP")
    sec_canonical = secondary_parents_canonical(secondary_parents)
    c_hash = content_hash(content)
    e_hash = embedding_hash(embedding)
    sa_hash = source_attribution_hash(source_attribution)
    parent = primary_parent_commit_hash or ("0x" + "00" * 32)
    s_root = compute_state_root(c_hash, e_hash, parent, sa_hash, creator, timestamp)
    c_commit = compute_commit_hash(s_root, parent, sec_canonical, creator, timestamp)
    return {
        "content_hash": c_hash,
        "embedding_hash": e_hash,
        "source_attribution_hash": sa_hash,
        "state_root": s_root,
        "commit_hash": c_commit,
        "secondary_parents_canonical": sec_canonical,
        "parent_count": 1,
    }
