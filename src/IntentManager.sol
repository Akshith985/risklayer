// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { LiquidityVault } from "./LiquidityVault.sol";
import { ReentrancyGuard } from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract IntentManager is ReentrancyGuard {
    enum IntentStatus {
        None,
        Open,
        Approved,
        Rejected,
        Cancelled,
        Expired
    }

    struct Intent {
        uint256 id;
        address taker;
        address provider;
        uint256 amount;
        uint256 expiry;
        IntentStatus status;
    }

    LiquidityVault public immutable vault;
    address public immutable configurator;
    address public riskOracle;

    uint256 public nextIntentId = 1;

    mapping(uint256 => Intent) private intents;

    error ZeroAddress();
    error ZeroAmount();
    error InvalidProvider();
    error InvalidExpiry();
    error IntentNotFound();
    error Unauthorized();
    error IntentNotOpen();
    error IntentNotExpired();
    error AlreadyConfigured();

    event RiskOracleConfigured(address indexed oracle);
    event IntentCreated(
        uint256 indexed intentId,
        address indexed taker,
        address indexed provider,
        uint256 amount,
        uint256 expiry
    );
    event IntentApproved(uint256 indexed intentId);
    event IntentRejected(uint256 indexed intentId);
    event IntentCancelled(uint256 indexed intentId);
    event IntentExpired(uint256 indexed intentId);

    constructor(LiquidityVault vault_) {
        if (address(vault_) == address(0)) revert ZeroAddress();

        vault = vault_;
        configurator = msg.sender;
    }

    modifier onlyRiskOracle() {
        if (msg.sender != riskOracle) revert Unauthorized();
        _;
    }

    function configureRiskOracle(address oracle) external {
        if (msg.sender != configurator) revert Unauthorized();
        if (riskOracle != address(0)) revert AlreadyConfigured();
        if (oracle == address(0)) revert ZeroAddress();

        riskOracle = oracle;

        emit RiskOracleConfigured(oracle);
    }

    function createIntent(address provider, uint256 amount, uint256 expiry)
        external
        nonReentrant
        returns (uint256 intentId)
    {
        if (provider == address(0)) revert ZeroAddress();
        if (provider == msg.sender) revert InvalidProvider();
        if (amount == 0) revert ZeroAmount();
        if (expiry <= block.timestamp) revert InvalidExpiry();

        intentId = nextIntentId++;

        vault.reserve(provider, amount);

        intents[intentId] = Intent({
            id: intentId,
            taker: msg.sender,
            provider: provider,
            amount: amount,
            expiry: expiry,
            status: IntentStatus.Open
        });

        emit IntentCreated(intentId, msg.sender, provider, amount, expiry);
    }

    // Only the configured RiskOracle can resolve an open intent.
    function resolveIntent(uint256 intentId, bool approved) external nonReentrant onlyRiskOracle {
        Intent storage intent = intents[intentId];

        if (intent.status == IntentStatus.None) {
            revert IntentNotFound();
        }

        if (intent.status != IntentStatus.Open) {
            revert IntentNotOpen();
        }

        if (block.timestamp >= intent.expiry) {
            revert IntentNotExpired();
        }

        if (approved) {
            intent.status = IntentStatus.Approved;
            emit IntentApproved(intentId);
        } else {
            intent.status = IntentStatus.Rejected;
            vault.release(intent.provider, intent.amount);
            emit IntentRejected(intentId);
        }
    }

    function cancelIntent(uint256 intentId) external nonReentrant {
        Intent storage intent = intents[intentId];

        if (intent.status == IntentStatus.None) {
            revert IntentNotFound();
        }

        if (intent.status != IntentStatus.Open) {
            revert IntentNotOpen();
        }

        if (msg.sender != intent.taker) revert Unauthorized();

        if (block.timestamp >= intent.expiry) {
            revert IntentNotExpired();
        }

        intent.status = IntentStatus.Cancelled;
        vault.release(intent.provider, intent.amount);

        emit IntentCancelled(intentId);
    }

    function expireIntent(uint256 intentId) external nonReentrant {
        Intent storage intent = intents[intentId];

        if (intent.status == IntentStatus.None) {
            revert IntentNotFound();
        }

        if (intent.status != IntentStatus.Open && intent.status != IntentStatus.Approved) {
            revert IntentNotOpen();
        }

        if (block.timestamp < intent.expiry) {
            revert IntentNotExpired();
        }

        intent.status = IntentStatus.Expired;
        vault.release(intent.provider, intent.amount);

        emit IntentExpired(intentId);
    }

    function getIntent(uint256 intentId) external view returns (Intent memory) {
        if (intents[intentId].status == IntentStatus.None) {
            revert IntentNotFound();
        }

        return intents[intentId];
    }
}
