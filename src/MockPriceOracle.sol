// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

/// @title MockPriceOracle — mock price feed for the Threshold Guardian demo.
/// @notice Emits PriceUpdated on every price change. The Guardian (Lasna) subscribes to it.
/// @dev Price uses 18 decimals (e.g. 100 ether = $100).
contract MockPriceOracle {
    uint256 public price;
    address public owner;

    event PriceUpdated(uint256 price, uint256 updatedAt);

    error NotOwner(address sender);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner(msg.sender);
        _;
    }

    constructor(uint256 initialPrice_) {
        owner = msg.sender;
        price = initialPrice_;
    }

    function setPrice(uint256 newPrice_) external onlyOwner {
        price = newPrice_;
        emit PriceUpdated(newPrice_, block.timestamp);
    }
}
