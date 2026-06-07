// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title MemoryRegistry — ownership and provenance layer for AI memory repositories
/// @notice Cognition lives off-chain. Ownership lives on Monad.
/// @dev MVP: linear history only. Merge commits disabled (parentCount must be 1).
contract MemoryRegistry is Ownable {
    constructor() Ownable(msg.sender) {}

    enum Visibility {
        PRIVATE,
        LICENSED,
        PUBLIC
    }

    struct MemoryCommit {
        bytes32 commitHash;
        bytes32 primaryParentCommitHash;
        uint8 parentCount;
        bytes32 contentHash;
        bytes32 embeddingHash;
        bytes32 sourceAttributionHash;
        bytes32 stateRoot;
        uint256 timestamp;
        address creator;
    }

    struct MemoryRepository {
        address owner;
        bytes32 headCommitHash;
        uint256 parentMemoryId;
        bytes32 forkPointCommitHash;
        Visibility visibility;
        string metadataURI;
        uint256 createdAt;
    }

    struct StructuralLineageResult {
        uint256 memoryId;
        uint256[] ancestorRepoIds;
        bytes32[] headToGenesisCommits;
        bool repositoryChainValid;
        bool forkLinksValid;
        bool commitParentChainValid;
    }

    uint256 public nextMemoryId = 1;

    mapping(uint256 => MemoryRepository) public repositories;
    mapping(uint256 => mapping(bytes32 => MemoryCommit)) public commits;
    mapping(uint256 => bytes32[]) public commitHistory;
    mapping(uint256 => mapping(bytes32 => bytes32[])) public secondaryParents;

    event RepositoryRegistered(uint256 indexed memoryId, address indexed owner, bytes32 genesisCommitHash);
    event CommitRecorded(uint256 indexed memoryId, bytes32 indexed commitHash, bytes32 primaryParent);
    event RepositoryForked(uint256 indexed parentId, uint256 indexed childId, address indexed owner);
    event RepositoryTransferred(uint256 indexed memoryId, address from, address to);
    event VisibilityUpdated(uint256 indexed memoryId, Visibility visibility);
    event MetadataURIUpdated(uint256 indexed memoryId, string metadataURI);

    error NotOwner();
    error InvalidPrimaryParent();
    error MergeCommitsDisabled();
    error CommitExists();
    error CommitNotFound();
    error InvalidRepository();
    error InvalidForkPoint();

    modifier onlyRepoOwner(uint256 memoryId) {
        if (repositories[memoryId].owner != msg.sender) revert NotOwner();
        _;
    }

    function registerRepository(
        bytes32 genesisCommitHash,
        bytes32 primaryParentCommitHash,
        uint8 parentCount,
        bytes32 secondaryParentsCanonical,
        bytes32 contentHash,
        bytes32 embeddingHash,
        bytes32 sourceAttributionHash,
        bytes32 stateRoot,
        string calldata metadataURI,
        Visibility visibility
    ) external returns (uint256 memoryId) {
        memoryId = nextMemoryId++;
        repositories[memoryId] = MemoryRepository({
            owner: msg.sender,
            headCommitHash: bytes32(0),
            parentMemoryId: 0,
            forkPointCommitHash: bytes32(0),
            visibility: visibility,
            metadataURI: metadataURI,
            createdAt: block.timestamp
        });

        _recordCommit(
            memoryId,
            genesisCommitHash,
            primaryParentCommitHash,
            parentCount,
            secondaryParentsCanonical,
            new bytes32[](0),
            contentHash,
            embeddingHash,
            sourceAttributionHash,
            stateRoot
        );

        emit RepositoryRegistered(memoryId, msg.sender, genesisCommitHash);
    }

    function createCommit(
        uint256 memoryId,
        bytes32 commitHash,
        bytes32 primaryParentCommitHash,
        uint8 parentCount,
        bytes32 secondaryParentsCanonical,
        bytes32[] calldata secondaryParentCommitHashes,
        bytes32 contentHash,
        bytes32 embeddingHash,
        bytes32 sourceAttributionHash,
        bytes32 stateRoot
    ) external onlyRepoOwner(memoryId) {
        _enforceMvpParentRules(parentCount, secondaryParentsCanonical, secondaryParentCommitHashes);

        MemoryRepository storage repo = repositories[memoryId];
        if (repo.headCommitHash == bytes32(0)) {
            if (primaryParentCommitHash != bytes32(0)) revert InvalidPrimaryParent();
        } else if (primaryParentCommitHash != repo.headCommitHash) {
            revert InvalidPrimaryParent();
        }

        _recordCommit(
            memoryId,
            commitHash,
            primaryParentCommitHash,
            parentCount,
            secondaryParentsCanonical,
            secondaryParentCommitHashes,
            contentHash,
            embeddingHash,
            sourceAttributionHash,
            stateRoot
        );
    }

    function forkRepository(
        uint256 parentMemoryId,
        bytes32 forkPointCommitHash,
        bytes32 initialCommitHash,
        bytes32 primaryParentCommitHash,
        uint8 parentCount,
        bytes32 secondaryParentsCanonical,
        bytes32 contentHash,
        bytes32 embeddingHash,
        bytes32 sourceAttributionHash,
        bytes32 stateRoot,
        string calldata metadataURI,
        Visibility visibility
    ) external returns (uint256 childMemoryId) {
        if (repositories[parentMemoryId].owner == address(0)) revert InvalidRepository();
        if (commits[parentMemoryId][forkPointCommitHash].commitHash == bytes32(0)) revert InvalidForkPoint();

        childMemoryId = nextMemoryId++;
        repositories[childMemoryId] = MemoryRepository({
            owner: msg.sender,
            headCommitHash: forkPointCommitHash,
            parentMemoryId: parentMemoryId,
            forkPointCommitHash: forkPointCommitHash,
            visibility: visibility,
            metadataURI: metadataURI,
            createdAt: block.timestamp
        });

        _recordCommit(
            childMemoryId,
            initialCommitHash,
            primaryParentCommitHash,
            parentCount,
            secondaryParentsCanonical,
            new bytes32[](0),
            contentHash,
            embeddingHash,
            sourceAttributionHash,
            stateRoot
        );

        emit RepositoryForked(parentMemoryId, childMemoryId, msg.sender);
    }

    function transferRepository(uint256 memoryId, address newOwner) external onlyRepoOwner(memoryId) {
        address from = repositories[memoryId].owner;
        repositories[memoryId].owner = newOwner;
        emit RepositoryTransferred(memoryId, from, newOwner);
    }

    function setVisibility(uint256 memoryId, Visibility visibility) external onlyRepoOwner(memoryId) {
        repositories[memoryId].visibility = visibility;
        emit VisibilityUpdated(memoryId, visibility);
    }

    function updateMetadataURI(uint256 memoryId, string calldata metadataURI) external onlyRepoOwner(memoryId) {
        repositories[memoryId].metadataURI = metadataURI;
        emit MetadataURIUpdated(memoryId, metadataURI);
    }

    function getRepositoryLineage(uint256 memoryId) external view returns (uint256[] memory) {
        uint256 count = 0;
        uint256 current = memoryId;
        while (current != 0) {
            count++;
            current = repositories[current].parentMemoryId;
        }
        uint256[] memory lineage = new uint256[](count);
        current = memoryId;
        for (uint256 i = 0; i < count; i++) {
            lineage[i] = current;
            current = repositories[current].parentMemoryId;
        }
        return lineage;
    }

    function getCommitHistory(uint256 memoryId) external view returns (bytes32[] memory) {
        return commitHistory[memoryId];
    }

    function getCommit(uint256 memoryId, bytes32 commitHash) external view returns (MemoryCommit memory) {
        return commits[memoryId][commitHash];
    }

    function getSecondaryParents(uint256 memoryId, bytes32 commitHash) external view returns (bytes32[] memory) {
        return secondaryParents[memoryId][commitHash];
    }

    /// @notice Structural provenance verification only — no hash recomputation
    function verifyLineage(uint256 memoryId)
        external
        view
        returns (StructuralLineageResult[] memory repoChain, bool structurallyValid)
    {
        uint256[] memory lineage = this.getRepositoryLineage(memoryId);
        repoChain = new StructuralLineageResult[](lineage.length);
        structurallyValid = true;

        for (uint256 i = 0; i < lineage.length; i++) {
            uint256 repoId = lineage[i];
            StructuralLineageResult memory result = _verifyRepoStructure(repoId);
            repoChain[i] = result;
            if (!result.repositoryChainValid || !result.forkLinksValid || !result.commitParentChainValid) {
                structurallyValid = false;
            }
        }
    }

    function _verifyRepoStructure(uint256 memoryId) internal view returns (StructuralLineageResult memory result) {
        MemoryRepository storage repo = repositories[memoryId];
        result.memoryId = memoryId;
        result.repositoryChainValid = repo.owner != address(0);

        if (repo.parentMemoryId != 0) {
            result.forkLinksValid = commits[repo.parentMemoryId][repo.forkPointCommitHash].commitHash != bytes32(0);
        } else {
            result.forkLinksValid = true;
        }

        bytes32[] storage history = commitHistory[memoryId];
        result.headToGenesisCommits = new bytes32[](history.length);
        result.commitParentChainValid = true;

        // commitHistory is stored genesis → head; validate in that order.
        for (uint256 i = 0; i < history.length; i++) {
            bytes32 hash = history[i];
            MemoryCommit storage c = commits[memoryId][hash];
            if (c.commitHash == bytes32(0)) {
                result.commitParentChainValid = false;
                continue;
            }
            if (i == 0) {
                if (c.primaryParentCommitHash != bytes32(0)) {
                    result.commitParentChainValid = false;
                }
            } else if (c.primaryParentCommitHash != history[i - 1]) {
                result.commitParentChainValid = false;
            }
            if (c.parentCount != 1) {
                result.commitParentChainValid = false;
            }
        }

        // Expose HEAD → genesis for callers.
        for (uint256 i = 0; i < history.length; i++) {
            result.headToGenesisCommits[i] = history[history.length - 1 - i];
        }

        uint256[] memory ancestors = new uint256[](1);
        ancestors[0] = memoryId;
        if (repo.parentMemoryId != 0) {
            ancestors = this.getRepositoryLineage(memoryId);
        }
        result.ancestorRepoIds = ancestors;
    }

    function _recordCommit(
        uint256 memoryId,
        bytes32 commitHash,
        bytes32 primaryParentCommitHash,
        uint8 parentCount,
        bytes32 secondaryParentsCanonical,
        bytes32[] memory secondaryParentCommitHashes,
        bytes32 contentHash,
        bytes32 embeddingHash,
        bytes32 sourceAttributionHash,
        bytes32 stateRoot
    ) internal {
        if (commits[memoryId][commitHash].commitHash != bytes32(0)) revert CommitExists();
        _enforceMvpParentRules(parentCount, secondaryParentsCanonical, secondaryParentCommitHashes);

        commits[memoryId][commitHash] = MemoryCommit({
            commitHash: commitHash,
            primaryParentCommitHash: primaryParentCommitHash,
            parentCount: parentCount,
            contentHash: contentHash,
            embeddingHash: embeddingHash,
            sourceAttributionHash: sourceAttributionHash,
            stateRoot: stateRoot,
            timestamp: block.timestamp,
            creator: msg.sender
        });

        commitHistory[memoryId].push(commitHash);
        repositories[memoryId].headCommitHash = commitHash;

        emit CommitRecorded(memoryId, commitHash, primaryParentCommitHash);
    }

    function _enforceMvpParentRules(
        uint8 parentCount,
        bytes32 secondaryParentsCanonical,
        bytes32[] memory secondaryParentCommitHashes
    ) internal pure {
        if (parentCount != 1) revert MergeCommitsDisabled();
        if (secondaryParentsCanonical != bytes32(0)) revert MergeCommitsDisabled();
        if (secondaryParentCommitHashes.length > 0) revert MergeCommitsDisabled();
    }
}
