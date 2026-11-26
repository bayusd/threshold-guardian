// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Test } from "forge-std/Test.sol";
import { MockPriceOracle } from "../src/MockPriceOracle.sol";

contract MockPriceOracleTest is Test {
    MockPriceOracle oracle;

    function setUp() public {
        oracle = new MockPriceOracle(100 ether);
    }

    function testInitialPrice() public view {
        assertEq(oracle.price(), 100 ether);
        assertEq(oracle.owner(), address(this));
    }

    function testSetPriceEmitsEvent() public {
        vm.expectEmit(true, false, false, true, address(oracle));
        emit MockPriceOracle.PriceUpdated(42 ether, block.timestamp);
        oracle.setPrice(42 ether);
        assertEq(oracle.price(), 42 ether);
    }

    function testSetPriceOnlyOwner() public {
        vm.prank(address(0xBEEF));
        vm.expectRevert(abi.encodeWithSelector(MockPriceOracle.NotOwner.selector, address(0xBEEF)));
        oracle.setPrice(1 ether);
    }
}
