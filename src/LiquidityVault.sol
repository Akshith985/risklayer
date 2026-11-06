// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import { IERC20 } from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import { SafeERC20 } from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import { ReentrancyGuard } from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract LiquidityVault is ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public immutable asset;
    address public immutable configurator;
    address public intentManager;

    mapping(address => uint256) public deposits;
    mapping(address => uint256) public reserved;

    uint256 public totalDeposits;

    error ZeroAddress();
    error ZeroAmount();
    error Unauthorized();
    error AlreadyConfigured();
    error InsufficientDeposit(uint256 available, uint256 requested);
    error InsufficientReserved(uint256 available, uint256 requested);
    error UnsupportedTokenBehavior();

    event Deposited(address indexed provider, uint256 amount);
    event Withdrawn(address indexed provider, uint256 amount);
    event LiquidityReserved(address indexed provider, uint256 amount);
    event LiquidityReleased(address indexed provider, uint256 amount);
    event IntentManagerConfigured(address indexed manager);

    constructor(IERC20 asset_) {
        if (address(asset_) == address(0)) revert ZeroAddress();

        asset = asset_;
        configurator = msg.sender;
    }

    modifier onlyIntentManager() {
        if (msg.sender != intentManager) revert Unauthorized();
        _;
    }

    // One-time setup. The configurator cannot replace the manager afterward.
    function configureIntentManager(address manager) external {
        if (msg.sender != configurator) revert Unauthorized();
        if (intentManager != address(0)) revert AlreadyConfigured();
        if (manager == address(0)) revert ZeroAddress();

        intentManager = manager;
        emit IntentManagerConfigured(manager);
    }

    function deposit(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        uint256 balanceBefore = asset.balanceOf(address(this));

        asset.safeTransferFrom(msg.sender, address(this), amount);

        uint256 received = asset.balanceOf(address(this)) - balanceBefore;

        if (received != amount) revert UnsupportedTokenBehavior();

        deposits[msg.sender] += amount;
        totalDeposits += amount;

        emit Deposited(msg.sender, amount);
    }

    function withdraw(uint256 amount) external nonReentrant {
        if (amount == 0) revert ZeroAmount();

        uint256 available = availableDeposit(msg.sender);

        if (amount > available) {
            revert InsufficientDeposit(available, amount);
        }

        deposits[msg.sender] -= amount;
        totalDeposits -= amount;

        asset.safeTransfer(msg.sender, amount);

        emit Withdrawn(msg.sender, amount);
    }

    function reserve(address provider, uint256 amount) external onlyIntentManager {
        if (amount == 0) revert ZeroAmount();

        uint256 available = availableDeposit(provider);

        if (amount > available) {
            revert InsufficientDeposit(available, amount);
        }

        reserved[provider] += amount;

        emit LiquidityReserved(provider, amount);
    }

    function release(address provider, uint256 amount) external onlyIntentManager {
        if (amount == 0) revert ZeroAmount();

        uint256 currentlyReserved = reserved[provider];

        if (amount > currentlyReserved) {
            revert InsufficientReserved(currentlyReserved, amount);
        }

        reserved[provider] -= amount;

        emit LiquidityReleased(provider, amount);
    }

    function availableDeposit(address provider) public view returns (uint256) {
        return deposits[provider] - reserved[provider];
    }

    function accountedAssets() external view returns (uint256) {
        return totalDeposits;
    }
}
