// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { IPayable } from "@reactive/src/interfaces/IPayable.sol";
import { AbstractPayer } from "@reactive/src/base/AbstractPayer.sol";
import { AbstractCallback } from "@reactive/src/base/AbstractCallback.sol";
import { Vault } from "../src/Vault.sol";

/// @notice Minimal stand-in for the Base Sepolia callback proxy.
contract MockProxy is IPayable {
    receive() external payable {}

    function debt(address) external pure returns (uint256) {
        return 0;
    }
}

contract VaultTest is Test {
    MockProxy proxy;
    Vault vault;
    address guardian = address(0xBEEF);

    function setUp() public {
        proxy = new MockProxy();
        vault = new Vault(IPayable(payable(address(proxy))), guardian);
    }

    function testDepositWithdraw() public {
        vault.deposit(100 ether);
        assertEq(vault.balances(address(this)), 100 ether);
        assertEq(vault.totalDeposits(), 100 ether);
        vault.withdraw(40 ether);
        assertEq(vault.balances(address(this)), 60 ether);
        assertEq(vault.totalDeposits(), 60 ether);
    }

    function testWithdrawMoreThanBalanceReverts() public {
        vault.deposit(10 ether);
        vm.expectRevert(abi.encodeWithSelector(Vault.InsufficientBalance.selector, 11 ether, 10 ether));
        vault.withdraw(11 ether);
    }

    function testPauseBlocksWithdraw() public {
        vault.deposit(10 ether);
        vm.prank(address(proxy));
        vault.pause(guardian, 40 ether);
        assertTrue(vault.paused());
        vm.expectRevert(Vault.VaultIsPaused.selector);
        vault.withdraw(1 ether);
    }

    function testPauseOnlyFromProxy() public {
        vm.expectRevert(
            abi.encodeWithSelector(AbstractPayer.NotAuthorized.selector, address(this), address(proxy))
        );
        vault.pause(guardian, 40 ether);
    }

    function testPauseWrongGuardianReverts() public {
        vm.prank(address(proxy));
        vm.expectRevert(
            abi.encodeWithSelector(AbstractCallback.CallbackNotAuthorized.selector, address(0xCAFE), guardian)
        );
        vault.pause(address(0xCAFE), 40 ether);
    }

    function testUnpauseReopens() public {
        vault.deposit(10 ether);
        vm.prank(address(proxy));
        vault.pause(guardian, 40 ether);
        vm.prank(address(proxy));
        vault.unpause(guardian, 60 ether);
        assertFalse(vault.paused());
        vault.withdraw(10 ether);
        assertEq(vault.balances(address(this)), 0);
    }

    function testEmergencyExitOnlyWhenPaused() public {
        vault.deposit(10 ether);
        vm.expectRevert(Vault.VaultNotPaused.selector);
        vault.emergencyExit(address(this));
        vm.prank(address(proxy));
        vault.pause(guardian, 40 ether);
        vm.expectEmit(true, false, false, true, address(vault));
        emit Vault.EmergencyExit(address(this), 10 ether);
        vault.emergencyExit(address(this));
        assertEq(vault.totalDeposits(), 0);
    }

    function testUnpauseManualOnlyOwner() public {
        vm.prank(address(proxy));
        vault.pause(guardian, 40 ether);
        vm.prank(address(0xBEEF));
        vm.expectRevert(abi.encodeWithSelector(Vault.NotOwner.selector, address(0xBEEF)));
        vault.unpauseManual();
        vault.unpauseManual();
        assertFalse(vault.paused());
    }
}
