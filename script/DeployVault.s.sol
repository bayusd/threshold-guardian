// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Script, console } from "forge-std/Script.sol";
import { IPayable } from "@reactive/src/interfaces/IPayable.sol";
import { Vault } from "../src/Vault.sol";

/// @notice Step 3: deploy the callback Vault on Base Sepolia (needs GUARDIAN_ADDRESS).
/// @dev Run: GUARDIAN_ADDRESS=0x... forge script script/DeployVault.s.sol --rpc-url $BASE_SEPOLIA_RPC --broadcast --private-key $PRIVATE_KEY
contract DeployVault is Script {
    address constant CALLBACK_PROXY_BASE = 0x476F44b11F5C942c58f4c8E3d0300E5710743585;

    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address guardian = vm.envAddress("GUARDIAN_ADDRESS");
        vm.startBroadcast(deployerKey);
        Vault vault = new Vault{ value: 0.00005 ether }(IPayable(payable(CALLBACK_PROXY_BASE)), guardian);
        vm.stopBroadcast();
        console.log("Vault:", address(vault));
    }
}
