// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Test} from "forge-std/Test.sol";
import {MemoryToken} from "../src/MemoryToken.sol";
import {MemoryRegistry} from "../src/MemoryRegistry.sol";

contract MemoryRegistryTest is Test {
    MemoryToken mem;
    MemoryRegistry registry;
    address alice = address(0xA11CE);
    address bob = address(0xB0B);

    function setUp() public {
        mem = new MemoryToken();
        registry = new MemoryRegistry();
    }

    function testRegisterAndCommit() public {
        vm.startPrank(alice);
        bytes32 genesis = keccak256("genesis");
        uint256 id = registry.registerRepository(
            genesis,
            bytes32(0),
            1,
            bytes32(0),
            keccak256("content"),
            keccak256("embedding"),
            keccak256("attr"),
            keccak256("state"),
            "ipfs://meta",
            MemoryRegistry.Visibility.PUBLIC
        );
        assertEq(id, 1);

        bytes32 commit2 = keccak256("commit2");
        registry.createCommit(
            id,
            commit2,
            genesis,
            1,
            bytes32(0),
            new bytes32[](0),
            keccak256("c2"),
            keccak256("e2"),
            keccak256("a2"),
            keccak256("s2")
        );
        vm.stopPrank();

        (, bytes32 head,,,,,) = registry.repositories(id);
        assertEq(head, commit2);
    }

    function testForkOwnership() public {
        vm.startPrank(alice);
        bytes32 genesis = keccak256("genesis");
        uint256 parentId = registry.registerRepository(
            genesis, bytes32(0), 1, bytes32(0),
            keccak256("c"), keccak256("e"), keccak256("a"), keccak256("s"),
            "uri", MemoryRegistry.Visibility.PUBLIC
        );
        vm.stopPrank();

        vm.startPrank(bob);
        uint256 childId = registry.forkRepository(
            parentId, genesis, keccak256("child"),
            genesis, 1, bytes32(0),
            keccak256("c"), keccak256("e"), keccak256("a"), keccak256("s"),
            "uri2", MemoryRegistry.Visibility.LICENSED
        );
        vm.stopPrank();

        (address childOwner,,,,,,) = registry.repositories(childId);
        (address parentOwner,,,,,,) = registry.repositories(parentId);
        assertEq(childOwner, bob);
        assertEq(parentOwner, alice);
    }

    function testVerifyLineageLinearRepo() public {
        vm.startPrank(alice);
        bytes32 genesis = keccak256("genesis");
        uint256 id = registry.registerRepository(
            genesis, bytes32(0), 1, bytes32(0),
            keccak256("c"), keccak256("e"), keccak256("a"), keccak256("s"),
            "uri", MemoryRegistry.Visibility.PUBLIC
        );
        bytes32 commit2 = keccak256("commit2");
        registry.createCommit(
            id, commit2, genesis, 1, bytes32(0), new bytes32[](0),
            keccak256("c2"), keccak256("e2"), keccak256("a2"), keccak256("s2")
        );
        bytes32 commit3 = keccak256("commit3");
        registry.createCommit(
            id, commit3, commit2, 1, bytes32(0), new bytes32[](0),
            keccak256("c3"), keccak256("e3"), keccak256("a3"), keccak256("s3")
        );
        vm.stopPrank();

        (MemoryRegistry.StructuralLineageResult[] memory repoChain, bool valid) =
            registry.verifyLineage(id);
        assertTrue(valid);
        assertEq(repoChain.length, 1);
        assertTrue(repoChain[0].repositoryChainValid);
        assertTrue(repoChain[0].forkLinksValid);
        assertTrue(repoChain[0].commitParentChainValid);
        assertEq(repoChain[0].headToGenesisCommits.length, 3);
        assertEq(repoChain[0].headToGenesisCommits[0], commit3);
        assertEq(repoChain[0].headToGenesisCommits[2], genesis);
    }

    function testMergeCommitsDisabled() public {
        vm.startPrank(alice);
        bytes32 genesis = keccak256("genesis");
        uint256 id = registry.registerRepository(
            genesis, bytes32(0), 1, bytes32(0),
            keccak256("c"), keccak256("e"), keccak256("a"), keccak256("s"),
            "uri", MemoryRegistry.Visibility.PUBLIC
        );
        vm.expectRevert(MemoryRegistry.MergeCommitsDisabled.selector);
        registry.createCommit(
            id, keccak256("bad"), genesis, 2, bytes32(uint256(1)),
            new bytes32[](1), keccak256("c"), keccak256("e"), keccak256("a"), keccak256("s")
        );
        vm.stopPrank();
    }
}
