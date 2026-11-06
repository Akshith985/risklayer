// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { Test } from "forge-std/Test.sol";

import { MockUSDC } from "./mocks/MockUSDC.sol";
import { LiquidityVault } from "../src/LiquidityVault.sol";
import { IntentManager } from "../src/IntentManager.sol";

contract IntentManagerTest is Test {
    MockUSDC token;
    LiquidityVault vault;
    IntentManager manager;

    address constant PROVIDER = address(0xBEEF);
    address constant TAKER = address(0xCAFE);
    address constant OTHER = address(0x1234);

    uint256 constant DEPOSIT = 1_000e6;
    uint256 constant TRADE = 200e6;

    function setUp() public {
        token = new MockUSDC();
        vault = new LiquidityVault(token);
        manager = new IntentManager(vault);

        vault.configureIntentManager(address(manager));
        manager.configureRiskOracle(OTHER);

        token.mint(PROVIDER, DEPOSIT);

        vm.startPrank(PROVIDER);
        token.approve(address(vault), DEPOSIT);
        vault.deposit(DEPOSIT);
        vm.stopPrank();
    }

    function testCreateIntentReservesLiquidity() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        IntentManager.Intent memory intent = manager.getIntent(id);

        assertEq(intent.taker, TAKER);
        assertEq(intent.provider, PROVIDER);
        assertEq(intent.amount, TRADE);
        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Open));

        assertEq(vault.reserved(PROVIDER), TRADE);
        assertEq(vault.availableDeposit(PROVIDER), DEPOSIT - TRADE);
    }

    function testCancelIntentReleasesLiquidity() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(TAKER);
        manager.cancelIntent(id);

        IntentManager.Intent memory intent = manager.getIntent(id);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Cancelled));

        assertEq(vault.reserved(PROVIDER), 0);
        assertEq(vault.availableDeposit(PROVIDER), DEPOSIT);
    }

    function testCannotCancelAnotherUsersIntent() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(OTHER);
        vm.expectRevert(IntentManager.Unauthorized.selector);
        manager.cancelIntent(id);
    }

    function testExpireIntentReleasesLiquidity() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.warp(block.timestamp + 1 hours);

        manager.expireIntent(id);

        IntentManager.Intent memory intent = manager.getIntent(id);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Expired));

        assertEq(vault.reserved(PROVIDER), 0);
        assertEq(vault.availableDeposit(PROVIDER), DEPOSIT);
    }

    function testCannotExpireBeforeDeadline() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.expectRevert(IntentManager.IntentNotExpired.selector);
        manager.expireIntent(id);
    }

    function testCannotReserveMoreThanAvailable() public {
        vm.prank(TAKER);

        vm.expectRevert(
            abi.encodeWithSelector(
                LiquidityVault.InsufficientDeposit.selector, DEPOSIT, DEPOSIT + 1
            )
        );

        manager.createIntent(PROVIDER, DEPOSIT + 1, block.timestamp + 1 hours);
    }

    function testProviderCannotWithdrawReservedLiquidity() public {
        vm.prank(TAKER);

        manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(PROVIDER);

        vm.expectRevert(
            abi.encodeWithSelector(
                LiquidityVault.InsufficientDeposit.selector, DEPOSIT - TRADE, DEPOSIT
            )
        );

        vault.withdraw(DEPOSIT);
    }

    function testMultipleIntentsCannotOverReserve() public {
        vm.startPrank(TAKER);

        manager.createIntent(PROVIDER, 600e6, block.timestamp + 1 hours);

        vm.expectRevert(
            abi.encodeWithSelector(LiquidityVault.InsufficientDeposit.selector, 400e6, 500e6)
        );

        manager.createIntent(PROVIDER, 500e6, block.timestamp + 1 hours);

        vm.stopPrank();
    }

    function testOnlyConfiguredManagerCanReserve() public {
        vm.prank(OTHER);

        vm.expectRevert(LiquidityVault.Unauthorized.selector);
        vault.reserve(PROVIDER, TRADE);
    }

    function testOnlyRiskOracleCanResolveIntent() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.expectRevert(IntentManager.Unauthorized.selector);
        manager.resolveIntent(id, true);
    }

    function testOracleApprovalUpdatesIntentStatus() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(OTHER);
        manager.resolveIntent(id, true);

        IntentManager.Intent memory intent = manager.getIntent(id);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Approved));

        assertEq(vault.reserved(PROVIDER), TRADE);
        assertEq(vault.availableDeposit(PROVIDER), DEPOSIT - TRADE);
    }

    function testOracleRejectionReleasesLiquidity() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(OTHER);
        manager.resolveIntent(id, false);

        IntentManager.Intent memory intent = manager.getIntent(id);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Rejected));

        assertEq(vault.reserved(PROVIDER), 0);
        assertEq(vault.availableDeposit(PROVIDER), DEPOSIT);
    }

    function testCannotResolveIntentTwice() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(OTHER);
        manager.resolveIntent(id, true);

        vm.prank(OTHER);
        vm.expectRevert(IntentManager.IntentNotOpen.selector);
        manager.resolveIntent(id, false);
    }

    function testApprovedIntentCanExpire() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(OTHER);
        manager.resolveIntent(id, true);

        vm.warp(block.timestamp + 1 hours);

        manager.expireIntent(id);

        IntentManager.Intent memory intent = manager.getIntent(id);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Expired));

        assertEq(vault.reserved(PROVIDER), 0);
        assertEq(vault.availableDeposit(PROVIDER), DEPOSIT);
    }

    function testRejectedIntentCannotBeCancelled() public {
        vm.prank(TAKER);

        uint256 id = manager.createIntent(PROVIDER, TRADE, block.timestamp + 1 hours);

        vm.prank(OTHER);
        manager.resolveIntent(id, false);

        vm.prank(TAKER);
        vm.expectRevert(IntentManager.IntentNotOpen.selector);
        manager.cancelIntent(id);
    }
}

