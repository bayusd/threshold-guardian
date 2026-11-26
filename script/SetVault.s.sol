// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import { Script, console } from "forge-std/Script.sol";
import { Guardian } from "../src/Guardian.sol";

/// @notice Step 4: point the Guardian at the Vault (needs GUARDIAN_ADDRESS + VAULT_ADDRESS).
/// @dev Run: GUARDIAN_ADDRESS=0x... VAULT_ADDRESS=0x... forge script script/SetVault.s.sol --rpc-url $LASNA_RPC --broadcast --private-key $PRIVATE_KEY
contract SetVault is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("PRIVATE_KEY");
        address guardianAddr = vm.envAddress("GUARDIAN_ADDRESS");
        address vault = vm.envAddress("VAULT_ADDRESS");
        vm.startBroadcast(deployerKey);
        Guardian(payable(guardianAddr)).setVault(vault);
        vm.stopBroadcast();
        console.log("Guardian:", guardianAddr);
        console.log("Vault set to:", vault);
    }
}
