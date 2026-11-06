// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { Test } from "forge-std/Test.sol";
import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

import { LiquidityVault } from "../src/LiquidityVault.sol";
import { MockUSDC } from "./mocks/MockUSDC.sol";

contract LiquidityVaultTest is Test {
    LiquidityVault internal vault;
    MockUSDC internal token;

    address internal constant ALICE = address(0xA11CE);
    address internal constant BOB = address(0xB0B);

    uint256 internal constant INITIAL_BALANCE = 10_000e6;

    function setUp() public {
        token = new MockUSDC();

        vault = new LiquidityVault(IERC20(address(token)));

        token.mint(ALICE, INITIAL_BALANCE);
        token.mint(BOB, INITIAL_BALANCE);
    }

    function testDeposit() public {
        uint256 amount = 100e6;

        vm.startPrank(ALICE);

        token.approve(address(vault), amount);
        vault.deposit(amount);

        vm.stopPrank();

        assertEq(vault.deposits(ALICE), amount);
        assertEq(vault.totalDeposits(), amount);
        assertEq(token.balanceOf(address(vault)), amount);
    }

    function testWithdraw() public {
        uint256 amount = 100e6;

        vm.startPrank(ALICE);

        token.approve(address(vault), amount);
        vault.deposit(amount);
        vault.withdraw(amount);

        vm.stopPrank();

        assertEq(vault.deposits(ALICE), 0);
        assertEq(vault.totalDeposits(), 0);
        assertEq(token.balanceOf(ALICE), INITIAL_BALANCE);
    }

    function testMultipleProviders() public {
        uint256 aliceAmount = 100e6;
        uint256 bobAmount = 250e6;

        vm.startPrank(ALICE);
        token.approve(address(vault), aliceAmount);
        vault.deposit(aliceAmount);
        vm.stopPrank();

        vm.startPrank(BOB);
        token.approve(address(vault), bobAmount);
        vault.deposit(bobAmount);
        vm.stopPrank();

        assertEq(vault.deposits(ALICE), aliceAmount);
        assertEq(vault.deposits(BOB), bobAmount);
        assertEq(vault.totalDeposits(), aliceAmount + bobAmount);
    }

    function testCannotDepositZero() public {
        vm.expectRevert(LiquidityVault.ZeroAmount.selector);

        vm.prank(ALICE);
        vault.deposit(0);
    }

    function testCannotWithdrawZero() public {
        vm.expectRevert(LiquidityVault.ZeroAmount.selector);

        vm.prank(ALICE);
        vault.withdraw(0);
    }

    function testCannotWithdrawMoreThanDeposited() public {
        uint256 amount = 100e6;

        vm.startPrank(ALICE);
        token.approve(address(vault), amount);
        vault.deposit(amount);
        vm.stopPrank();

        vm.expectRevert(
            abi.encodeWithSelector(LiquidityVault.InsufficientDeposit.selector, amount, amount + 1)
        );

        vm.prank(ALICE);
        vault.withdraw(amount + 1);
    }

    function testCannotWithdrawAnotherProvidersDeposit() public {
        uint256 amount = 100e6;

        vm.startPrank(ALICE);
        token.approve(address(vault), amount);
        vault.deposit(amount);
        vm.stopPrank();

        vm.expectRevert(
            abi.encodeWithSelector(LiquidityVault.InsufficientDeposit.selector, 0, amount)
        );

        vm.prank(BOB);
        vault.withdraw(amount);
    }

    function testDirectTransferDoesNotCreditProvider() public {
        uint256 amount = 100e6;

        vm.prank(ALICE);
        token.transfer(address(vault), amount);

        assertEq(vault.deposits(ALICE), 0);
        assertEq(vault.totalDeposits(), 0);
        assertEq(token.balanceOf(address(vault)), amount);
    }

    function testFuzzDepositAndWithdraw(uint96 amount) public {
        vm.assume(amount > 0);

        token.mint(ALICE, amount);

        vm.startPrank(ALICE);

        token.approve(address(vault), amount);
        vault.deposit(amount);

        assertEq(vault.deposits(ALICE), amount);

        vault.withdraw(amount);

        vm.stopPrank();

        assertEq(vault.deposits(ALICE), 0);
        assertEq(vault.totalDeposits(), 0);
    }
}
