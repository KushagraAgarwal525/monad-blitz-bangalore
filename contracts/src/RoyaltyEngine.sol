// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {MemoryRegistry} from "./MemoryRegistry.sol";
import {PaymentType} from "./interfaces/IPaymentTypes.sol";

/// @title RoyaltyEngine — upstream contribution rewards for memory licensing
contract RoyaltyEngine is Ownable, ReentrancyGuard {
    struct RoyaltyRule {
        uint256 ancestorMemoryId;
        uint16 bps;
    }

    MemoryRegistry public immutable registry;
    IERC20 public immutable memToken;

    mapping(uint256 => RoyaltyRule[]) public royaltyRules;

    event RoyaltyRulesSet(uint256 indexed memoryId, uint256 ruleCount);
    event RoyaltyDistributed(
        uint256 indexed memoryId, address indexed recipient, uint256 amount, PaymentType paymentType
    );

    error InvalidBpsSum();
    error PaymentTypeNotSupported();

    constructor(address registry_, address memToken_) Ownable(msg.sender) {
        registry = MemoryRegistry(registry_);
        memToken = IERC20(memToken_);
    }

    function setRoyaltyRules(uint256 memoryId, RoyaltyRule[] calldata rules) external onlyOwner {
        delete royaltyRules[memoryId];
        uint256 total;
        for (uint256 i = 0; i < rules.length; i++) {
            total += rules[i].bps;
            royaltyRules[memoryId].push(rules[i]);
        }
        if (total > 10000) revert InvalidBpsSum();
        emit RoyaltyRulesSet(memoryId, rules.length);
    }

    function inheritRoyaltyRules(uint256 childMemoryId, uint256 parentMemoryId, uint16 parentBps) external onlyOwner {
        RoyaltyRule[] storage parentRules = royaltyRules[parentMemoryId];
        for (uint256 i = 0; i < parentRules.length; i++) {
            royaltyRules[childMemoryId].push(parentRules[i]);
        }
        royaltyRules[childMemoryId].push(RoyaltyRule({ancestorMemoryId: parentMemoryId, bps: parentBps}));
    }

    function calculateRoyaltySplit(uint256 memoryId, uint256 amount, PaymentType paymentType)
        public
        view
        returns (address[] memory recipients, uint256[] memory amounts)
    {
        if (paymentType != PaymentType.MEM) revert PaymentTypeNotSupported();
        RoyaltyRule[] storage rules = royaltyRules[memoryId];
        recipients = new address[](rules.length + 1);
        amounts = new uint256[](rules.length + 1);
        uint256 distributed;

        for (uint256 i = 0; i < rules.length; i++) {
            uint256 share = (amount * rules[i].bps) / 10000;
            amounts[i] = share;
            distributed += share;
            (address ancestorOwner,,,,,,) = registry.repositories(rules[i].ancestorMemoryId);
            recipients[i] = ancestorOwner;
        }
        (address repoOwner,,,,,,) = registry.repositories(memoryId);
        recipients[rules.length] = repoOwner;
        amounts[rules.length] = amount - distributed;
    }

    function distributeRoyalties(uint256 memoryId, uint256 amount, PaymentType paymentType)
        external
        nonReentrant
        returns (uint256 ownerShare)
    {
        if (paymentType != PaymentType.MEM) revert PaymentTypeNotSupported();
        (address[] memory recipients, uint256[] memory amounts) = calculateRoyaltySplit(memoryId, amount, paymentType);
        for (uint256 i = 0; i < recipients.length; i++) {
            if (amounts[i] > 0) {
                require(memToken.transferFrom(msg.sender, recipients[i], amounts[i]), "Transfer failed");
                emit RoyaltyDistributed(memoryId, recipients[i], amounts[i], paymentType);
            }
            if (i == recipients.length - 1) {
                ownerShare = amounts[i];
            }
        }
    }
}
