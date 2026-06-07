// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {MemoryRegistry} from "./MemoryRegistry.sol";
import {RoyaltyEngine} from "./RoyaltyEngine.sol";
import {PaymentType} from "./interfaces/IPaymentTypes.sol";

/// @title LicenseManager — commercial access rights for memory repositories
contract LicenseManager is Ownable, ReentrancyGuard {
    enum LicenseType {
        Permanent,
        Monthly,
        Daily
    }

    struct License {
        address licensee;
        LicenseType licenseType;
        uint256 startTime;
        uint256 endTime;
        uint256 pricePaid;
        PaymentType paymentType;
        bool active;
    }

    MemoryRegistry public immutable registry;
    RoyaltyEngine public immutable royaltyEngine;
    IERC20 public immutable memToken;

    mapping(uint256 => mapping(address => License)) public licenses;
    mapping(LicenseType => uint256) public memPrices;

    event LicensePurchased(
        uint256 indexed memoryId,
        address indexed licensee,
        LicenseType licenseType,
        uint256 pricePaid,
        PaymentType paymentType
    );
    event RevenueRecorded(uint256 indexed memoryId, address indexed payer, uint256 amount, PaymentType paymentType);
    event LicenseRevoked(uint256 indexed memoryId, address indexed licensee);

    error PaymentTypeNotSupported();
    error InvalidPrice();
    error NotRepoOwner();

    constructor(address registry_, address royaltyEngine_, address memToken_) Ownable(msg.sender) {
        registry = MemoryRegistry(registry_);
        royaltyEngine = RoyaltyEngine(royaltyEngine_);
        memToken = IERC20(memToken_);
        memPrices[LicenseType.Permanent] = 100 ether;
        memPrices[LicenseType.Monthly] = 10 ether;
        memPrices[LicenseType.Daily] = 1 ether;
    }

    function setMemPrice(LicenseType licenseType, uint256 price) external onlyOwner {
        memPrices[licenseType] = price;
    }

    function buyLicense(uint256 memoryId, LicenseType licenseType, PaymentType paymentType)
        external
        nonReentrant
        returns (uint256 price)
    {
        if (paymentType != PaymentType.MEM) revert PaymentTypeNotSupported();
        price = memPrices[licenseType];
        if (price == 0) revert InvalidPrice();

        require(memToken.transferFrom(msg.sender, address(this), price), "Payment failed");
        require(memToken.approve(address(royaltyEngine), price), "Approve failed");
        royaltyEngine.distributeRoyalties(memoryId, price, PaymentType.MEM);

        licenses[memoryId][msg.sender] = License({
            licensee: msg.sender,
            licenseType: licenseType,
            startTime: block.timestamp,
            endTime: type(uint256).max,
            pricePaid: price,
            paymentType: paymentType,
            active: true
        });

        emit LicensePurchased(memoryId, msg.sender, licenseType, price, paymentType);
        emit RevenueRecorded(memoryId, msg.sender, price, paymentType);
    }

    function rentLicense(uint256 memoryId, LicenseType licenseType, uint256 periods, PaymentType paymentType)
        external
        nonReentrant
        returns (uint256 price)
    {
        if (paymentType != PaymentType.MEM) revert PaymentTypeNotSupported();
        if (licenseType == LicenseType.Permanent) revert InvalidPrice();
        price = memPrices[licenseType] * periods;

        require(memToken.transferFrom(msg.sender, address(this), price), "Payment failed");
        require(memToken.approve(address(royaltyEngine), price), "Approve failed");
        royaltyEngine.distributeRoyalties(memoryId, price, PaymentType.MEM);

        uint256 duration = licenseType == LicenseType.Monthly ? 30 days * periods : 1 days * periods;
        licenses[memoryId][msg.sender] = License({
            licensee: msg.sender,
            licenseType: licenseType,
            startTime: block.timestamp,
            endTime: block.timestamp + duration,
            pricePaid: price,
            paymentType: paymentType,
            active: true
        });

        emit LicensePurchased(memoryId, msg.sender, licenseType, price, paymentType);
        emit RevenueRecorded(memoryId, msg.sender, price, paymentType);
    }

    function renewLicense(uint256 memoryId, PaymentType paymentType) external nonReentrant {
        License storage lic = licenses[memoryId][msg.sender];
        require(lic.active, "No license");
        if (paymentType != PaymentType.MEM) revert PaymentTypeNotSupported();
        uint256 price = memPrices[lic.licenseType];
        require(memToken.transferFrom(msg.sender, address(this), price), "Payment failed");
        require(memToken.approve(address(royaltyEngine), price), "Approve failed");
        royaltyEngine.distributeRoyalties(memoryId, price, PaymentType.MEM);
        if (lic.licenseType == LicenseType.Monthly) {
            lic.endTime += 30 days;
        } else if (lic.licenseType == LicenseType.Daily) {
            lic.endTime += 1 days;
        }
        lic.pricePaid += price;
        emit RevenueRecorded(memoryId, msg.sender, price, paymentType);
    }

    function revokeLicense(uint256 memoryId, address licensee) external {
        (address owner,,,,,,) = registry.repositories(memoryId);
        if (owner != msg.sender) revert NotRepoOwner();
        licenses[memoryId][licensee].active = false;
        emit LicenseRevoked(memoryId, licensee);
    }

    function hasActiveLicense(uint256 memoryId, address user) external view returns (bool) {
        License storage lic = licenses[memoryId][user];
        return lic.active && block.timestamp <= lic.endTime;
    }
}
