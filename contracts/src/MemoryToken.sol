// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {ERC20} from "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title MemoryToken (MEM) — utility token for Memoria licensing and royalties
contract MemoryToken is ERC20, Ownable {
    constructor() ERC20("MemoryToken", "MEM") Ownable(msg.sender) {}

    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    function faucet(address to, uint256 amount) external {
        require(amount <= 1000 ether, "Faucet limit");
        _mint(to, amount);
    }
}
