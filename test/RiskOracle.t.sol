// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { Test } from "forge-std/Test.sol";

import { MockUSDC } from "./mocks/MockUSDC.sol";
import { LiquidityVault } from "../src/LiquidityVault.sol";
import { IntentManager } from "../src/IntentManager.sol";
import { RiskOracle } from "../src/RiskOracle.sol";

contract RiskOracleTest is Test {
    MockUSDC token;
    LiquidityVault vault;
    IntentManager manager;
    RiskOracle oracle;

    uint256 constant KEY1 = 0xA11CE;
    uint256 constant KEY2 = 0xB0B;
    uint256 constant KEY3 = 0xCAFE;
    uint256 constant KEY4 = 0xD00D;
    uint256 constant KEY5 = 0x123456;

    address constant PROVIDER = address(0xBEEF);
    address constant TAKER = address(0xCAFE1);

    uint256 constant AMOUNT = 200e6;

    uint256 intentId;
    uint64 validUntil;

    function setUp() public {
        address node1 = vm.addr(KEY1);
        address node2 = vm.addr(KEY2);
        address node3 = vm.addr(KEY3);
        address node4 = vm.addr(KEY4);

        token = new MockUSDC();
        vault = new LiquidityVault(token);
        manager = new IntentManager(vault);

        vault.configureIntentManager(address(manager));

        address[4] memory nodes = [node1, node2, node3, node4];

        oracle = new RiskOracle(manager, nodes, 3);
        manager.configureRiskOracle(address(oracle));

        token.mint(PROVIDER, 1_000e6);

        vm.startPrank(PROVIDER);
        token.approve(address(vault), 1_000e6);
        vault.deposit(1_000e6);
        vm.stopPrank();

        vm.prank(TAKER);
        intentId = manager.createIntent(PROVIDER, AMOUNT, block.timestamp + 2 hours);

        validUntil = uint64(block.timestamp + 1 hours);
    }

    function makeSignature(
        uint256 privateKey,
        bool approved,
        uint16 riskScoreBps,
        uint256 maxAmount,
        uint16 spreadBps,
        uint16 collateralBps
    ) internal view returns (bytes memory) {
        bytes32 digest = oracle.getDigest(
            intentId,
            TAKER,
            PROVIDER,
            AMOUNT,
            approved,
            riskScoreBps,
            maxAmount,
            spreadBps,
            collateralBps,
            validUntil,
            0
        );

        (uint8 v, bytes32 r, bytes32 s) = vm.sign(privateKey, digest);

        return abi.encodePacked(r, s, v);
    }

    function makeSignatures(
        bool approved,
        uint16 riskScoreBps,
        uint256 maxAmount,
        uint16 spreadBps,
        uint16 collateralBps,
        uint256 key1,
        uint256 key2,
        uint256 key3
    ) internal view returns (bytes[] memory signatures) {
        signatures = new bytes[](3);

        signatures[0] =
            makeSignature(key1, approved, riskScoreBps, maxAmount, spreadBps, collateralBps);

        signatures[1] =
            makeSignature(key2, approved, riskScoreBps, maxAmount, spreadBps, collateralBps);

        signatures[2] =
            makeSignature(key3, approved, riskScoreBps, maxAmount, spreadBps, collateralBps);
    }

    function normalSignatures() internal view returns (bytes[] memory) {
        return makeSignatures(true, 2500, AMOUNT, 100, 1500, KEY1, KEY2, KEY3);
    }

    function testAcceptsThreeOfFourSignatures() public {
        oracle.submitAssessment(
            intentId, true, 2500, AMOUNT, 100, 1500, validUntil, normalSignatures()
        );

        RiskOracle.Assessment memory result = oracle.getAssessment(intentId);

        assertTrue(result.approved);
        assertEq(result.riskScoreBps, 2500);
        assertEq(result.maxAmount, AMOUNT);
        assertEq(result.signatures, 3);

        IntentManager.Intent memory intent = manager.getIntent(intentId);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Approved));

        assertEq(vault.reserved(PROVIDER), AMOUNT);
    }

    function testRejectsInsufficientSignatures() public {
        bytes[] memory signatures = new bytes[](2);

        signatures[0] = makeSignature(KEY1, true, 2500, AMOUNT, 100, 1500);

        signatures[1] = makeSignature(KEY2, true, 2500, AMOUNT, 100, 1500);

        vm.expectRevert(RiskOracle.InvalidSignatureCount.selector);

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, validUntil, signatures);
    }

    function testRejectsUnauthorizedNode() public {
        bytes[] memory signatures = makeSignatures(true, 2500, AMOUNT, 100, 1500, KEY1, KEY2, KEY5);

        vm.expectRevert(RiskOracle.UnauthorizedNode.selector);

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, validUntil, signatures);
    }

    function testRejectsDuplicateSignatures() public {
        bytes[] memory signatures = makeSignatures(true, 2500, AMOUNT, 100, 1500, KEY1, KEY1, KEY2);

        vm.expectRevert(RiskOracle.DuplicateSignature.selector);

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, validUntil, signatures);
    }

    function testRejectsModifiedAmount() public {
        bytes[] memory signatures = new bytes[](3);

        signatures[0] = makeSignature(KEY1, true, 2500, AMOUNT + 1, 100, 1500);

        signatures[1] = makeSignature(KEY2, true, 2500, AMOUNT + 1, 100, 1500);

        signatures[2] = makeSignature(KEY3, true, 2500, AMOUNT + 1, 100, 1500);

        vm.expectRevert(RiskOracle.UnauthorizedNode.selector);

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, validUntil, signatures);
    }

    function testRejectsExpiredAssessment() public {
        bytes[] memory signatures = normalSignatures();

        uint64 expiredAt = uint64(block.timestamp);

        vm.expectRevert(RiskOracle.AssessmentExpired.selector);

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, expiredAt, signatures);
    }

    function testRejectsAssessmentReplay() public {
        bytes[] memory signatures = normalSignatures();

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, validUntil, signatures);

        vm.expectRevert(RiskOracle.AssessmentAlreadySubmitted.selector);

        oracle.submitAssessment(intentId, true, 2500, AMOUNT, 100, 1500, validUntil, signatures);
    }

    function testAcceptsRejectedAssessment() public {
        bytes[] memory signatures = makeSignatures(false, 8000, 0, 500, 3000, KEY1, KEY2, KEY3);

        oracle.submitAssessment(intentId, false, 8000, 0, 500, 3000, validUntil, signatures);

        RiskOracle.Assessment memory result = oracle.getAssessment(intentId);

        assertFalse(result.approved);
        assertEq(result.riskScoreBps, 8000);
        assertEq(result.maxAmount, 0);
        assertEq(result.signatures, 3);

        IntentManager.Intent memory intent = manager.getIntent(intentId);

        assertEq(uint256(intent.status), uint256(IntentManager.IntentStatus.Rejected));

        assertEq(vault.reserved(PROVIDER), 0);
        assertEq(vault.availableDeposit(PROVIDER), 1_000e6);
    }

    function testRejectsInvalidRiskScore() public {
        bytes[] memory signatures = normalSignatures();

        vm.expectRevert(RiskOracle.InvalidAssessment.selector);

        oracle.submitAssessment(intentId, true, 10001, AMOUNT, 100, 1500, validUntil, signatures);
    }

    function testRejectedAssessmentCannotBeSubmittedAgain() public {
        bytes[] memory signatures = makeSignatures(false, 8000, 0, 500, 3000, KEY1, KEY2, KEY3);

        oracle.submitAssessment(intentId, false, 8000, 0, 500, 3000, validUntil, signatures);

        vm.expectRevert(RiskOracle.AssessmentAlreadySubmitted.selector);

        oracle.submitAssessment(intentId, false, 8000, 0, 500, 3000, validUntil, signatures);
    }

    function testAssessmentNonceIncrements() public {
        oracle.submitAssessment(
            intentId, true, 2500, AMOUNT, 100, 1500, validUntil, normalSignatures()
        );

        assertEq(oracle.assessmentNonce(intentId), 1);
    }
}

