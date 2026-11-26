// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { ISystemContract } from "@reactive/src/interfaces/ISystemContract.sol";
import { IReactive } from "@reactive/src/interfaces/IReactive.sol";
import { AbstractPayer } from "@reactive/src/base/AbstractPayer.sol";
import { Guardian } from "../src/Guardian.sol";

/// @notice Minimal stand-in for the Lasna system contract, etched at the real SYSTEM address.
contract MockSystem {
    uint256 public subscribeCalls;
    uint256 public callbackCalls;
    uint256 public lastCallbackChainId;
    address public lastCallbackRecipient;
    uint64 public lastCallbackGasLimit;
    bytes public lastCallbackPayload;

    function subscribe(uint256, address, uint256, uint256, uint256, uint256) external {
        subscribeCalls++;
    }

    function unsubscribe(uint256, address, uint256, uint256, uint256, uint256) external {}

    function requestCallback(ISystemContract.CallbackVersion, bytes memory) external {}

    function requestCallbackV_1_0(ISystemContract.CallbackConfiguration_V_1_0 memory config_) external {
        callbackCalls++;
        lastCallbackChainId = config_.chainId;
        lastCallbackRecipient = config_.recipient;
        lastCallbackGasLimit = config_.gasLimit;
        lastCallbackPayload = config_.payload;
    }

    function debt(address) external pure returns (uint256) {
        return 0;
    }

    function reserves(address) external pure returns (uint256) {
        return 0;
    }

    function depositTo(address) external payable {}

    receive() external payable {}
}

contract GuardianTest is Test {
    address constant SYSTEM = 0x8888888888888888888888888888888888888888;
    address oracle = address(0x0BAD);
    address vault = address(0xCA11);
    uint256 threshold = 50 ether;

    MockSystem mockSystem;
    MockSystem systemMock; // same code, etched at SYSTEM — state lives here
    Guardian guardian;

    function setUp() public {
        mockSystem = new MockSystem();
        vm.etch(SYSTEM, address(mockSystem).code);
        systemMock = MockSystem(payable(SYSTEM));
        guardian = new Guardian(oracle, threshold);
        guardian.setVault(vault);
    }

    function _log(uint256 price_, uint256 topic0_, uint256 opCode_) internal view returns (IReactive.LogRecord memory) {
        return IReactive.LogRecord({
            chainId: 84532,
            contractAddress: oracle,
            topic0: topic0_,
            topic1: 0,
            topic2: 0,
            topic3: 0,
            data: abi.encode(price_, block.timestamp),
            blockNumber: 1,
            opCode: opCode_,
            blockHash: 0,
            txHash: 0,
            logIndex: 0
        });
    }

    /// @dev Evaluates the topic BEFORE vm.prank: prank is consumed by the next call,
    /// so any getter call in react()'s arguments would eat it.
    function _react(uint256 price_, uint256 topic0_, uint256 opCode_) internal {
        IReactive.LogRecord memory log_ = _log(price_, topic0_, opCode_);
        vm.prank(SYSTEM);
        guardian.react(log_);
    }

    function testConstructorSubscribes() public view {
        assertEq(systemMock.subscribeCalls(), 1);
        assertEq(guardian.oracle(), oracle);
        assertEq(guardian.threshold(), threshold);
    }

    function testReactBelowThresholdRequestsPause() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        _react(40 ether, topic, 1);
        assertTrue(guardian.alertActive());
        assertEq(guardian.pauseCallbacks(), 1);
        assertEq(guardian.lastPrice(), 40 ether);
        assertEq(systemMock.callbackCalls(), 1);
        assertEq(systemMock.lastCallbackChainId(), 84532);
        assertEq(systemMock.lastCallbackRecipient(), vault);
        assertEq(systemMock.lastCallbackGasLimit(), 500_000);
        assertEq(
            systemMock.lastCallbackPayload(),
            abi.encodeWithSignature("pause(address,uint256)", address(0), 40 ether)
        );
    }

    function testReactBelowThresholdTwiceRequestsOnce() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        _react(40 ether, topic, 1);
        _react(39 ether, topic, 1);
        assertEq(systemMock.callbackCalls(), 1);
        assertEq(guardian.pauseCallbacks(), 1);
    }

    function testReactAboveThresholdWhenInactiveDoesNothing() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        _react(60 ether, topic, 1);
        assertFalse(guardian.alertActive());
        assertEq(systemMock.callbackCalls(), 0);
    }

    function testReactRecoveryRequestsUnpause() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        _react(40 ether, topic, 1);
        _react(60 ether, topic, 1);
        assertFalse(guardian.alertActive());
        assertEq(guardian.unpauseCallbacks(), 1);
        assertEq(systemMock.callbackCalls(), 2);
        assertEq(
            systemMock.lastCallbackPayload(),
            abi.encodeWithSignature("unpause(address,uint256)", address(0), 60 ether)
        );
    }

    function testReactWrongTopicIgnored() public {
        _react(40 ether, uint256(keccak256("Other(uint256)")), 1);
        assertFalse(guardian.alertActive());
        assertEq(systemMock.callbackCalls(), 0);
        assertEq(guardian.lastPrice(), 0);
    }

    function testReactWrongOpCodeIgnored() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        _react(40 ether, topic, 2);
        assertFalse(guardian.alertActive());
        assertEq(systemMock.callbackCalls(), 0);
    }

    function testReactAtThresholdDoesNotTrigger() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        _react(50 ether, topic, 1);
        assertEq(systemMock.callbackCalls(), 0);
    }

    function testReactNonSystemReverts() public {
        uint256 topic = guardian.PRICE_UPDATED_TOPIC();
        IReactive.LogRecord memory log_ = _log(40 ether, topic, 1);
        vm.expectRevert(
            abi.encodeWithSelector(AbstractPayer.NotAuthorized.selector, address(this), SYSTEM)
        );
        guardian.react(log_);
    }

    function testSetVaultOnlyOwner() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert(abi.encodeWithSelector(Guardian.NotOwner.selector, address(0xBEEF)));
        guardian.setVault(address(0x1234));
    }

    function testNoVaultNoCallback() public {
        Guardian g2 = new Guardian(oracle, threshold);
        uint256 topic = g2.PRICE_UPDATED_TOPIC();
        IReactive.LogRecord memory log_ = _log(40 ether, topic, 1);
        vm.prank(SYSTEM);
        g2.react(log_);
        assertTrue(g2.alertActive());
        assertEq(systemMock.callbackCalls(), 0);
    }
}
