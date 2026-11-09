# RiskLayer

[![CI](https://github.com/Akshith985/risklayer/actions/workflows/test.yml/badge.svg)](https://github.com/Akshith985/risklayer/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Solidity](https://img.shields.io/badge/Solidity-0.8.24-363636.svg)](https://docs.soliditylang.org/)
[![Built with Foundry](https://img.shields.io/badge/Built%20with-Foundry-orange.svg)](https://book.getfoundry.sh/)

**An on-chain liquidity reservation protocol gated by a quorum of independent risk nodes.**
**Backend : [https://risklayer.onrender.com]Here**
**Site : [https://risklayer-1.onrender.com]Here**
Liquidity providers deposit funds into a vault. When a taker opens a payment *intent* against a
provider, that provider's liquidity is reserved. An off-chain committee of risk nodes then scores the
intent and signs an [EIP-712](https://eips.ethereum.org/EIPS/eip-712) assessment. The `RiskOracle`
contract verifies a **3-of-4 signature quorum** on-chain and approves or rejects the intent, releasing
the reserved liquidity on rejection.

> **Status: experimental, testnet only, unaudited.** Do not use with real funds. See
> [Known limitations](#known-limitations) and [SECURITY.md](SECURITY.md).

## Table of contents

- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Smart contracts](#smart-contracts)
- [Risk nodes](#risk-nodes)
- [Getting started](#getting-started)
- [Testing](#testing)
- [Deployment](#deployment)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

## How it works

1. A **provider** deposits USDC into the `LiquidityVault`.
2. A **taker** calls `IntentManager.createIntent(provider, amount, expiry)`. The vault reserves
   `amount` of the provider's deposit, so it cannot be withdrawn.
3. The backend runs the four **risk nodes** on the intent. Each node independently computes a risk
   score and signs the result with its own key.
4. Anyone submits the collected signatures to `RiskOracle.submitAssessment(...)`.
5. The oracle rebuilds the EIP-712 digest from the **on-chain** intent, recovers each signer, and
   requires at least `quorum` distinct authorized nodes.
6. The oracle calls `IntentManager.resolveIntent`:
   - **Approved**: the intent moves to `Approved` and the liquidity stays reserved.
   - **Rejected**: the intent moves to `Rejected` and the liquidity is released.
7. A taker can `cancelIntent` while it is `Open`; anyone can `expireIntent` once it passes its expiry.

### Intent lifecycle

```
                 ┌──────────── cancelIntent (taker) ───────────► Cancelled
                 │
None ─ createIntent ─► Open ─ resolveIntent(true)  ─► Approved ─ expireIntent ─► Expired
                 │        └─ resolveIntent(false) ─► Rejected
                 └──────────── expireIntent (after expiry) ────► Expired
```

## Architecture

```
┌──────────────┐   HTTP    ┌──────────────────┐  imports  ┌──────────────────────┐
│  React app   │ ────────► │  FastAPI backend │ ────────► │  risk_nodes (Python) │
│ (ethers.js)  │           │  (web3.py reads) │           │  engine · signer ·   │
└──────┬───────┘           └────────┬─────────┘           │  aggregator          │
       │ MetaMask txs               │ contract reads      └──────────┬───────────┘
       │                            ▼                                │ EIP-712 signatures
       │                ┌───────────────────────────────────────────┐│
       └──────────────► │ LiquidityVault ◄─ IntentManager ◄─ RiskOracle ◄┘
                        └───────────────────────────────────────────┘
                                       EVM chain
```

- **Contracts** hold funds and enforce the lifecycle. They are the only source of truth.
- **Risk nodes** are pure functions of an intent plus features. They hold no state.
- **Backend** reads chain state, assembles the node payload, collects signatures and returns them. It
  never sends transactions.
- **Frontend** sends deposits, withdrawals and intent actions directly from the user's wallet, and
  submits the collected signatures to the oracle.

## Repository layout

```
.
├── src/                    # Solidity contracts (Foundry)
│   ├── LiquidityVault.sol
│   ├── IntentManager.sol
│   └── RiskOracle.sol
├── test/                   # Forge tests + mocks
├── script/                 # Foundry deploy scripts
├── risk_nodes/             # Off-chain risk engine, signer and aggregator (Python)
│   ├── nodes/
│   ├── scripts/            # Local lifecycle helper scripts
│   ├── tests/              # pytest suite
│   └── data/               # Sample payloads
├── backend/                # FastAPI service
├── frontend/               # React + Vite dashboard
├── foundry.toml
└── .github/workflows/      # CI
```

## Smart contracts

| Contract | Responsibility |
| --- | --- |
| [`LiquidityVault`](src/LiquidityVault.sol) | Custody of the ERC-20 asset. Tracks per-provider `deposits` and `reserved`. `reserve` and `release` are callable only by the `IntentManager`. Rejects fee-on-transfer tokens. |
| [`IntentManager`](src/IntentManager.sol) | Intent lifecycle (`Open → Approved / Rejected / Cancelled / Expired`). Reserves and releases vault liquidity. `resolveIntent` is callable only by the `RiskOracle`. |
| [`RiskOracle`](src/RiskOracle.sol) | EIP-712 verifier. Checks a quorum of distinct, authorized node signatures over the on-chain intent, stores the assessment, and resolves the intent. |

Design notes:

- Cross-contract wiring is **one-time**: `configureIntentManager` and `configureRiskOracle` can be
  called once, only by the deployer.
- Node set (4 addresses) and quorum (3) are fixed at `RiskOracle` construction.
- The signed message binds `intentId`, `taker`, `provider`, `amount`, the decision and risk
  parameters, `validUntil` and a `nonce`, under the domain `"RiskLayer RiskOracle"` version `"1"`.
- `LiquidityVault` and `IntentManager` use `ReentrancyGuard` on state-changing entry points, and all
  three contracts use custom errors.

### EIP-712 type

```
RiskAssessment(uint256 intentId,address taker,address provider,uint256 amount,bool approved,
uint16 riskScoreBps,uint256 maxAmount,uint16 spreadBps,uint16 collateralBps,uint64 validUntil,uint64 nonce)
```

The typehash in `RiskOracle.sol` and the type list in `risk_nodes/nodes/signer.py` **must stay
identical**. Change both together, or signatures will stop verifying.

## Risk nodes

`risk_nodes/` contains the off-chain half of the system:

- `risk_engine.py`: a deterministic, rule-based scorer. It adds weighted points for provider reversal
  rate, taker dispute rate, account age, transaction velocity, payment-method risk and provider
  capacity utilization, clamps the total to 10,000 bps, and approves when the score is below 7,000.
  Spread and collateral are derived from the score.
- `signer.py`: builds and signs the EIP-712 typed data, and recovers signers.
- `node.py`: one node. It validates the payload, runs the engine and signs the assessment.
- `aggregator.py`: runs the nodes, checks they agree on the assessment and digest, verifies each
  signature, and returns the signature set once quorum is reached.

## Getting started

### Prerequisites

- [Foundry](https://book.getfoundry.sh/getting-started/installation) (`forge`, `cast`, `anvil`)
- Python 3.10+
- A recent Node.js LTS and npm
- MetaMask (or another injected wallet) for the frontend

### 1. Clone and build the contracts

```bash
git clone --recurse-submodules https://github.com/Akshith985/risklayer.git
cd risklayer

forge build
forge test
```

If you cloned without `--recurse-submodules`, run `git submodule update --init --recursive`.

### 2. Generate risk node keys

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt eth-account pytest

cp risk_nodes/.env.example risk_nodes/.env
python risk_nodes/scripts/generate_keys.py
```

This fills `NODE_1_PRIVATE_KEY` ... `NODE_4_PRIVATE_KEY` in `risk_nodes/.env`. Never commit that file.

### 3. Point the deploy script at your node addresses

`script/DeployRiskLayer.s.sol` currently hardcodes the four authorized node addresses. Replace them with
the addresses of *your* keys, otherwise `submitAssessment` will revert with `UnauthorizedNode`:

```bash
cast wallet address --private-key <NODE_1_PRIVATE_KEY>   # repeat for nodes 2-4
```

### 4. Run a local chain and deploy

```bash
anvil                                   # in a separate terminal

export DEPLOYER_PRIVATE_KEY=<an Anvil account private key>
forge script script/DeployRiskLayer.s.sol:DeployRiskLayer \
  --rpc-url http://127.0.0.1:8545 --broadcast
```

The script deploys `MockUSDC`, `LiquidityVault`, `IntentManager` and `RiskOracle`, wires them together
and prints the addresses.

### 5. Run the backend

Create `backend/.env`:

```env
RPC_URL=http://127.0.0.1:8545
CHAIN_ID=31337
USDC_ADDRESS=0x...
VAULT_ADDRESS=0x...
MANAGER_ADDRESS=0x...
ORACLE_ADDRESS=0x...
# Optional: extra allowed CORS origins (comma-separated)
# FRONTEND_URLS=http://localhost:5173
```

```bash
cd backend
uvicorn app:app --reload        # http://127.0.0.1:8000  (docs at /docs)
```

The backend reads contract ABIs from `out/`, so run `forge build` first.

### 6. Run the frontend

```bash
cd frontend
npm install
echo "VITE_API_URL=http://127.0.0.1:8000" > .env.local
npm run dev                     # http://localhost:5173
```

> **Note:** the frontend is currently hardcoded to **Base Sepolia (chain ID 84532)** and will reject a
> backend on any other chain. To use it with a local Anvil chain you must change the chain constants at
> the top of `frontend/src/App.tsx`, or deploy to Base Sepolia (see below). Making this configurable is
> a good first issue.

## Testing

```bash
# Solidity
forge fmt --check
forge build --sizes
forge test -vvv

# Python risk nodes (run from risk_nodes/ so `nodes` and `config` import correctly)
cd risk_nodes && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

CI currently runs the Forge checks only; extending it to Python and the frontend is on the
[roadmap](#roadmap).

## Deployment

To deploy to Base Sepolia:

```bash
export DEPLOYER_PRIVATE_KEY=<funded testnet key>
forge script script/DeployRiskLayer.s.sol:DeployRiskLayer \
  --rpc-url https://sepolia.base.org --broadcast
```

Then set `RPC_URL=https://sepolia.base.org`, `CHAIN_ID=84532` and the printed contract addresses in
`backend/.env`. Use a throwaway key with testnet funds only.

## Known limitations

These are open problems, not hidden ones. Help is very welcome.

- **The four nodes run in a single process.** The aggregator loads all four keys from one `.env`, so
  the 3-of-4 quorum is not decentralized yet. The contract supports separate operators; the backend
  does not use it that way.
- **Risk features are user-supplied.** Only `amount` and provider capacity come from chain data. The
  reversal rate, dispute rate, account age, velocity and payment-method risk come from the request.
- **No settlement step.** An `Approved` intent keeps its liquidity reserved until `expireIntent` is called.
- **Node addresses are hardcoded** in the deploy script, and several helper scripts hardcode local
  Anvil addresses.
- **The CLI helper payloads are out of sync.** The saved JSON files in `risk_nodes/data/` and the
  output of `scripts/create_intent.py` place `chain_id` and `oracle_address` at the top level, while
  `nodes/node.py` and `nodes/aggregator.py` read them from inside `intent`. The backend builds the
  payload correctly.
- **Misleading error name.** `resolveIntent` and `cancelIntent` revert with `IntentNotExpired` when
  the intent has already expired.
- **Unaudited.** No formal security review has been done.

## Roadmap

- [ ] Run risk nodes as independent services operated by separate parties
- [ ] Source risk features from verifiable data instead of request parameters
- [ ] Add a settlement / fill path for approved intents
- [ ] Make node set and chain configuration environment-driven (deploy script, frontend)
- [ ] Fix the CLI payload shape and add an integration test covering it
- [ ] Add Python and frontend jobs to CI
- [ ] Fuzz and invariant tests for vault accounting and the oracle
- [ ] Independent security review

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first, and look for issues
labelled `good first issue` and `help wanted`.

## Security

Please do **not** open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md) for how to
report them privately.

## License

Released under the [MIT License](LICENSE).
