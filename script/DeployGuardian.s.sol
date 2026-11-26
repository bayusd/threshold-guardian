// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Script, console } from "forge-std/Script.sol";
import { Guardian } from "../src/Guardian.sol";

/// @notice Step 2: deploy the reactive Guardian on Lasna (needs ORACLE_ADDRESS).
/// @dev Run: ORACLE_ADDRESS=0x... forge script script/DeployGuardian.s.sol --rpc-url $LASNA_RPC --broadcast --private-key $PRIVATE_KEY
contract DeployGuardian is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address oracle = vm.envAddress("ORACLE_ADDRESS");
        vm.startBroadcast(deployerKey);
        Guardian guardian = new Guardian{ value: 0.001 ether }(oracle, 50 ether);
        vm.stopBroadcast();
        console.log("Guardian:", address(guardian));
    }
}
