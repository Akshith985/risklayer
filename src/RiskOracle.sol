// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { EIP712 } from "@openzeppelin/contracts/utils/cryptography/EIP712.sol";
import { ECDSA } from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

import { IntentManager } from "./IntentManager.sol";

contract RiskOracle is EIP712 {
    using ECDSA for bytes32;

    bytes32 public constant RISK_TYPEHASH = keccak256(
        "RiskAssessment(uint256 intentId,address taker,address provider,uint256 amount,bool approved,uint16 riskScoreBps,uint256 maxAmount,uint16 spreadBps,uint16 collateralBps,uint64 validUntil,uint64 nonce)"
    );

    uint256 public constant BPS_DENOMINATOR = 10_000;

    IntentManager public immutable intentManager;
    uint8 public immutable quorum;

    mapping(address => bool) public isNode;
    mapping(uint256 => bool) public assessmentSubmitted;
    mapping(uint256 => uint64) public assessmentNonce;

    struct Assessment {
        bool approved;
        uint16 riskScoreBps;
        uint256 maxAmount;
        uint16 spreadBps;
        uint16 collateralBps;
        uint64 validUntil;
        uint8 signatures;
    }

    mapping(uint256 => Assessment) public assessments;

    error ZeroAddress();
    error InvalidQuorum();
    error DuplicateNode();
    error UnauthorizedNode();
    error InvalidSignatureCount();
    error DuplicateSignature();
    error InvalidIntent();
    error AssessmentAlreadySubmitted();
    error AssessmentExpired();
    error InvalidAssessment();
    error InsufficientQuorum();

    event AssessmentVerified(
        uint256 indexed intentId, bool approved, uint16 riskScoreBps, uint8 signatures
    );

    constructor(IntentManager intentManager_, address[4] memory nodes, uint8 quorum_)
        EIP712("RiskLayer RiskOracle", "1")
    {
        if (address(intentManager_) == address(0)) {
            revert ZeroAddress();
        }

        if (quorum_ == 0 || quorum_ > 4) {
            revert InvalidQuorum();
        }

        intentManager = intentManager_;
        quorum = quorum_;

        for (uint256 i = 0; i < 4; i++) {
            if (nodes[i] == address(0)) revert ZeroAddress();
            if (isNode[nodes[i]]) revert DuplicateNode();

            isNode[nodes[i]] = true;
        }
    }

    function getDigest(
        uint256 intentId,
        address taker,
        address provider,
        uint256 amount,
        bool approved,
        uint16 riskScoreBps,
        uint256 maxAmount,
        uint16 spreadBps,
        uint16 collateralBps,
        uint64 validUntil,
        uint64 nonce
    ) public view returns (bytes32) {
        bytes32 structHash = keccak256(
            abi.encode(
                RISK_TYPEHASH,
                intentId,
                taker,
                provider,
                amount,
                approved,
                riskScoreBps,
                maxAmount,
                spreadBps,
                collateralBps,
                validUntil,
                nonce
            )
        );

        return _hashTypedDataV4(structHash);
    }

    function submitAssessment(
        uint256 intentId,
        bool approved,
        uint16 riskScoreBps,
        uint256 maxAmount,
        uint16 spreadBps,
        uint16 collateralBps,
        uint64 validUntil,
        bytes[] calldata signatures
    ) external {
        if (assessmentSubmitted[intentId]) {
            revert AssessmentAlreadySubmitted();
        }

        if (signatures.length < quorum || signatures.length > 4) {
            revert InvalidSignatureCount();
        }

        IntentManager.Intent memory intent = intentManager.getIntent(intentId);

        if (intent.status != IntentManager.IntentStatus.Open || intent.amount == 0) {
            revert InvalidIntent();
        }

        if (block.timestamp >= validUntil || validUntil > intent.expiry) {
            revert AssessmentExpired();
        }

        if (
            riskScoreBps > BPS_DENOMINATOR || spreadBps > BPS_DENOMINATOR
                || collateralBps > BPS_DENOMINATOR
        ) {
            revert InvalidAssessment();
        }

        if (approved && maxAmount < intent.amount) {
            revert InvalidAssessment();
        }

        uint64 nonce = assessmentNonce[intentId];

        bytes32 digest = getDigest(
            intentId,
            intent.taker,
            intent.provider,
            intent.amount,
            approved,
            riskScoreBps,
            maxAmount,
            spreadBps,
            collateralBps,
            validUntil,
            nonce
        );

        address[] memory recoveredNodes = new address[](signatures.length);

        for (uint256 i = 0; i < signatures.length; i++) {
            address signer = ECDSA.recover(digest, signatures[i]);

            if (!isNode[signer]) {
                revert UnauthorizedNode();
            }

            for (uint256 j = 0; j < i; j++) {
                if (recoveredNodes[j] == signer) {
                    revert DuplicateSignature();
                }
            }

            recoveredNodes[i] = signer;
        }

        if (recoveredNodes.length < quorum) {
            revert InsufficientQuorum();
        }

        assessmentSubmitted[intentId] = true;
        assessmentNonce[intentId]++;

        assessments[intentId] = Assessment({
            approved: approved,
            riskScoreBps: riskScoreBps,
            maxAmount: maxAmount,
            spreadBps: spreadBps,
            collateralBps: collateralBps,
            validUntil: validUntil,
            signatures: uint8(signatures.length)
        });

        // Resolve the intent through its authorized lifecycle controller.
        // A rejected intent releases its reserved liquidity in IntentManager.
        intentManager.resolveIntent(intentId, approved);

        emit AssessmentVerified(intentId, approved, riskScoreBps, uint8(signatures.length));
    }

    function getAssessment(uint256 intentId) external view returns (Assessment memory) {
        return assessments[intentId];
    }
}
