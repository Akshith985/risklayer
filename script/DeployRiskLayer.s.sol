// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { Script } from "forge-std/Script.sol";
import { console2 } from "forge-std/console2.sol";

import { MockUSDC } from "../test/mocks/MockUSDC.sol";
import { LiquidityVault } from "../src/LiquidityVault.sol";
import { IntentManager } from "../src/IntentManager.sol";
import { RiskOracle } from "../src/RiskOracle.sol";

contract DeployRiskLayer is Script {
    function run() external {
        uint256 deployerKey = vm.envUint("DEPLOYER_PRIVATE_KEY");

        address[4] memory nodes;

        nodes[0] = vm.parseAddress("0x4830f6Abc335faE46D8A194377bb0c846B849557");
        nodes[1] = vm.parseAddress("0x9372d8B570D1f1Da32712379E72e6932a5535d73");
        nodes[2] = vm.parseAddress("0x1edAa89807FeD15e08497d6f7483117ea709d859");
        nodes[3] = vm.parseAddress("0xf43356e777fC484ae2b603E8FA1c5C6f8f3921b9");

        vm.startBroadcast(deployerKey);

        MockUSDC token = new MockUSDC();
        LiquidityVault vault = new LiquidityVault(token);
        IntentManager manager = new IntentManager(vault);

        vault.configureIntentManager(address(manager));

        RiskOracle oracle = new RiskOracle(manager, nodes, 3);
        manager.configureRiskOracle(address(oracle));

        vm.stopBroadcast();

        console2.log("MockUSDC:", address(token));
        console2.log("LiquidityVault:", address(vault));
        console2.log("IntentManager:", address(manager));
        console2.log("RiskOracle:", address(oracle));
        console2.log("Risk node quorum:");
        console2.log(uint256(3));

        for (uint256 i = 0; i < nodes.length; i++) {
            console2.log("Authorized node:", nodes[i]);
        }
    }
}

