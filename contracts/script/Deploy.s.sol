// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {Script} from "forge-std/Script.sol";
import {console} from "forge-std/console.sol";
import {MemoryToken} from "../src/MemoryToken.sol";
import {MemoryRegistry} from "../src/MemoryRegistry.sol";
import {RoyaltyEngine} from "../src/RoyaltyEngine.sol";
import {LicenseManager} from "../src/LicenseManager.sol";
import {MemoryScoreRegistry} from "../src/MemoryScoreRegistry.sol";

contract Deploy is Script {
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerPrivateKey);

        MemoryToken mem = new MemoryToken();
        MemoryRegistry registry = new MemoryRegistry();
        RoyaltyEngine royalty = new RoyaltyEngine(address(registry), address(mem));
        LicenseManager license = new LicenseManager(address(registry), address(royalty), address(mem));
        MemoryScoreRegistry scoreRegistry = new MemoryScoreRegistry();

        vm.stopBroadcast();

        console.log("MemoryToken:", address(mem));
        console.log("MemoryRegistry:", address(registry));
        console.log("RoyaltyEngine:", address(royalty));
        console.log("LicenseManager:", address(license));
        console.log("MemoryScoreRegistry:", address(scoreRegistry));
    }
}
