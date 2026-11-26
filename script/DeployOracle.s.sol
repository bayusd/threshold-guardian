// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Script, console } from "forge-std/Script.sol";
import { MockPriceOracle } from "../src/MockPriceOracle.sol";

/// @notice Step 1: deploy the origin oracle on Base Sepolia (no dependencies).
/// @dev Run: forge script script/DeployOracle.s.sol --rpc-url $BASE_SEPOLIA_RPC --broadcast --private-key $PRIVATE_KEY
contract DeployOracle is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        vm.startBroadcast(deployerKey);
        MockPriceOracle oracle = new MockPriceOracle(100 ether);
        vm.stopBroadcast();
        console.log("MockPriceOracle:", address(oracle));
    }
}
