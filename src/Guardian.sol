// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { ISystemContract } from "@reactive/src/interfaces/ISystemContract.sol";
import { IReactive } from "@reactive/src/interfaces/IReactive.sol";
import { AbstractReactive } from "@reactive/src/base/AbstractReactive.sol";

/// @title Guardian — Threshold Guardian reactive contract (Lasna).
/// @notice Subscribes to MockPriceOracle.PriceUpdated on Base Sepolia. When the price
/// falls below `threshold` it requests a callback that pauses the Vault; when the price
/// recovers above threshold it requests a callback that unpauses it. One callback per
/// crossing (hysteresis via `alertActive`), so repeated below-threshold events are free.
contract Guardian is AbstractReactive {
    uint256 public constant DESTINATION_CHAIN_ID = 84532; // Base Sepolia
    uint256 public constant ORIGIN_CHAIN_ID = 84532; // Base Sepolia
    uint256 public constant PRICE_UPDATED_TOPIC = uint256(keccak256("PriceUpdated(uint256,uint256)"));
    uint64 public constant CALLBACK_GAS_LIMIT = 500_000;

    address public immutable oracle;
    address public immutable owner;
    uint256 public threshold;
    address public vault;
    bool public alertActive;
    uint256 public lastPrice;
    uint256 public lastPriceAt;
    uint256 public pauseCallbacks;
    uint256 public unpauseCallbacks;

    event ThresholdBreached(uint256 price, uint256 threshold, uint256 timestamp);
    event Recovered(uint256 price, uint256 threshold, uint256 timestamp);
    event VaultSet(address vault);
    event ThresholdSet(uint256 threshold);

    error NotOwner(address sender);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner(msg.sender);
        _;
    }

    constructor(address oracle_, uint256 threshold_) payable {
        oracle = oracle_;
        owner = msg.sender;
        threshold = threshold_;
        SYSTEM.subscribe(
            ORIGIN_CHAIN_ID, oracle_, PRICE_UPDATED_TOPIC, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE
        );
    }

    /// @notice Sets the callback recipient (Vault). Breaks the deploy cycle:
    /// deploy Guardian first, then Vault, then point the Guardian at it.
    function setVault(address vault_) external onlyOwner {
        vault = vault_;
        emit VaultSet(vault_);
    }

    function setThreshold(uint256 threshold_) external onlyOwner {
        threshold = threshold_;
        emit ThresholdSet(threshold_);
    }

    /// @inheritdoc IReactive
    function react(LogRecord calldata log_) external override onlySystem {
        if (log_.topic0 != PRICE_UPDATED_TOPIC || log_.opCode != 1) return;
        (uint256 price, uint256 updatedAt) = abi.decode(log_.data, (uint256, uint256));
        lastPrice = price;
        lastPriceAt = updatedAt;
        if (price < threshold && !alertActive) {
            alertActive = true;
            emit ThresholdBreached(price, threshold, updatedAt);
            if (_requestCallback("pause(address,uint256)", price)) pauseCallbacks++;
        } else if (price >= threshold && alertActive) {
            alertActive = false;
            emit Recovered(price, threshold, updatedAt);
            if (_requestCallback("unpause(address,uint256)", price)) unpauseCallbacks++;
        }
    }

    /// @notice Requests a pause/unpause callback to the Vault. No-op when no vault is set.
    /// @return sent True when a callback was requested.
    function _requestCallback(string memory signature_, uint256 price_) internal returns (bool sent) {
        if (vault == address(0)) return false;
        SYSTEM.requestCallbackV_1_0(
            ISystemContract.CallbackConfiguration_V_1_0({
                chainId: DESTINATION_CHAIN_ID,
                recipient: vault,
                gasLimit: CALLBACK_GAS_LIMIT,
                payload: abi.encodeWithSignature(signature_, address(0), price_)
            })
        );
        return true;
    }

    /// @notice Settles outstanding debt from this contract's balance.
    function coverDebt() external {
        _coverDebt();
    }
}
