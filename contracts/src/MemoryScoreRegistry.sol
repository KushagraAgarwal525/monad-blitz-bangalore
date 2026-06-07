// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title MemoryScoreRegistry — on-chain score snapshots for MemoryFi collateral prep
contract MemoryScoreRegistry is Ownable {
    constructor() Ownable(msg.sender) {}

    struct ScoreSnapshot {
        uint256 score;
        uint256 licenseRevenue;
        uint256 royaltyRevenue;
        uint256 forkCount;
        uint256 retrievalVolume;
        uint256 activeUsers;
        uint256 memoryAgeDays;
        uint256 recordedAt;
        bytes32 scoreHash;
    }

    mapping(uint256 => ScoreSnapshot[]) public scoreHistory;
    mapping(uint256 => uint256) public latestScore;

    event ScoreSnapshotRecorded(uint256 indexed memoryId, uint256 score, bytes32 scoreHash);

    function recordScoreSnapshot(uint256 memoryId, ScoreSnapshot calldata snapshot) external onlyOwner {
        scoreHistory[memoryId].push(snapshot);
        latestScore[memoryId] = snapshot.score;
        emit ScoreSnapshotRecorded(memoryId, snapshot.score, snapshot.scoreHash);
    }

    function getScoreHistoryLength(uint256 memoryId) external view returns (uint256) {
        return scoreHistory[memoryId].length;
    }
}
