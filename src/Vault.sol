// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { IPayable } from "@reactive/src/interfaces/IPayable.sol";
import { AbstractCallback } from "@reactive/src/base/AbstractCallback.sol";

/// @title Vault — mock vault protected by the Threshold Guardian.
/// @notice Deposits/withdrawals use a mock ledger (no real ETH moves). `pause`/`unpause`
/// can only be called through the Base Sepolia callback proxy by the authorized Guardian.
/// @dev Callback payloads are `pause(address,uint256)` / `unpause(address,uint256)`;
/// the proxy injects the Guardian address as the first argument.
contract Vault is AbstractCallback {
    bool public paused;
    uint256 public totalDeposits;
    mapping(address => uint256) public balances;
    address public owner;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event VaultPaused(address indexed guardian, uint256 price, uint256 timestamp);
    event VaultUnpaused(address indexed guardian, uint256 price, uint256 timestamp);
    event EmergencyExit(address indexed to, uint256 amount);

    error NotOwner(address sender);
    error VaultIsPaused();
    error VaultNotPaused();
    error InsufficientBalance(uint256 requested, uint256 available);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner(msg.sender);
        _;
    }

    constructor(IPayable callbackProxy_, address guardian_) payable AbstractCallback(callbackProxy_, guardian_) {
        owner = msg.sender;
    }

    /// @notice Mock deposit: credits the caller's ledger balance.
    function deposit(uint256 amount_) external {
        balances[msg.sender] += amount_;
        totalDeposits += amount_;
        emit Deposited(msg.sender, amount_);
    }

    /// @notice Mock withdrawal: blocked while the vault is paused by the Guardian.
    function withdraw(uint256 amount_) external {
        if (paused) revert VaultIsPaused();
        uint256 bal = balances[msg.sender];
        if (amount_ > bal) revert InsufficientBalance(amount_, bal);
        balances[msg.sender] = bal - amount_;
        totalDeposits -= amount_;
        emit Withdrawn(msg.sender, amount_);
    }

    /// @notice Called by the Guardian via the callback proxy when price falls below threshold.
    function pause(address reactive_, uint256 price_) external onlyServiceProvider onlyCallbackSender(reactive_) {
        paused = true;
        emit VaultPaused(reactive_, price_, block.timestamp);
    }

    /// @notice Called by the Guardian via the callback proxy when price recovers.
    function unpause(address reactive_, uint256 price_) external onlyServiceProvider onlyCallbackSender(reactive_) {
        paused = false;
        emit VaultUnpaused(reactive_, price_, block.timestamp);
    }

    /// @notice Owner escape hatch: unpause without waiting for a callback.
    function unpauseManual() external onlyOwner {
        paused = false;
        emit VaultUnpaused(msg.sender, 0, block.timestamp);
    }

    /// @notice Owner rescue: zeroes the mock ledger while paused and logs the exit.
    function emergencyExit(address to_) external onlyOwner {
        if (!paused) revert VaultNotPaused();
        uint256 amount = totalDeposits;
        totalDeposits = 0;
        emit EmergencyExit(to_, amount);
    }

    /// @notice Settles outstanding callback debt from this contract's balance.
    function coverDebt() external {
        _coverDebt();
    }
}
