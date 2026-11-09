# Contributing to RiskLayer

Thanks for your interest in RiskLayer. This project is experimental and welcomes contributions of all
sizes: bug reports, tests, documentation, design discussion and code.

By participating you agree to keep discussions respectful and constructive. Harassment or
discrimination of any kind is not tolerated.

## Ways to contribute

- **Report a bug** or unexpected behavior by opening an issue with reproduction steps.
- **Suggest an improvement** by opening an issue or a GitHub Discussion before starting large work.
- **Pick up an issue.** Look for `good first issue` and `help wanted`. Comment on the issue to claim it
  so work isn't duplicated.
- **Improve tests and docs.** More coverage and clearer explanations are always valuable.
- **Review pull requests.** Careful review of contract changes is especially useful.

> **Found a security vulnerability?** Do not open a public issue. Follow [SECURITY.md](SECURITY.md).

## Project layout

| Path | What it is |
| --- | --- |
| `src/`, `test/`, `script/` | Solidity contracts, Forge tests, deploy scripts |
| `risk_nodes/` | Python risk engine, EIP-712 signer and aggregator |
| `backend/` | FastAPI service |
| `frontend/` | React + Vite dashboard |

See the [README](README.md) for architecture and local setup.

## Development setup

```bash
git clone --recurse-submodules https://github.com/<your-username>/risklayer.git
cd risklayer

# Contracts
forge build && forge test

# Python
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt eth-account pytest
cd risk_nodes && pytest

# Frontend
cd frontend && npm install && npm run lint
```

Never commit `.env` files, private keys or mnemonics. Use throwaway keys for testing.

## Workflow

1. **Fork** the repo and create a branch from `master`:
   `git checkout -b feat/short-description`
2. Make focused changes. One logical change per pull request.
3. Add or update tests for the behavior you changed.
4. Run the checks listed below.
5. Open a pull request describing **what** changed and **why**, and link the issue it addresses.

### Branch and commit style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(oracle): reject assessments with duplicate node signatures
fix(backend): return 409 when an intent is already assessed
docs: clarify EIP-712 domain in README
test(vault): add fuzz test for reserve/release accounting
```

## Checks to run before opening a PR

```bash
# Solidity (these run in CI)
forge fmt --check
forge build --sizes
forge test -vvv

# Python
cd risk_nodes && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

A PR that fails the CI Forge checks will not be merged.

## Coding guidelines

### Solidity

- Target `solc 0.8.24` (see `foundry.toml`). Format with `forge fmt` (100-column lines, 4 spaces).
- Use **custom errors** rather than revert strings.
- Add NatSpec (`@notice`, `@param`, `@return`) to external and public functions.
- Follow checks-effects-interactions, and keep `nonReentrant` on functions that change state and make
  external calls.
- Every new `revert` path needs a test, and every new state transition needs a test for both the
  success case and the failure cases. Prefer fuzz tests for accounting logic.
- Keep access control explicit. Any new privileged function should say who can call it and why.

### EIP-712 changes

The signed type is defined in **two places** that must stay identical:

- `RISK_TYPEHASH` and `getDigest` in `src/RiskOracle.sol`
- `EIP712_TYPES` and the domain in `risk_nodes/nodes/signer.py`

If you change one, change the other and update the tests in `test/RiskOracle.t.sol` and
`risk_nodes/tests/test_signer.py`. State the change prominently in your PR description.

### Python

- Follow PEP 8 and add type hints to new functions.
- Keep the risk engine deterministic: the same input must always produce the same output, because the
  nodes must agree on the exact assessment.
- Add `pytest` tests for new scoring rules or validation.

### Frontend

- TypeScript, and keep `npm run lint` and `npm run build` clean.
- Avoid hardcoding chain IDs, addresses or URLs; prefer configuration.

## Pull request checklist

- [ ] The change is focused and the PR description explains the motivation
- [ ] Tests added or updated, and all checks pass locally
- [ ] No secrets, keys or `.env` files included
- [ ] Docs and README updated if behavior or setup changed
- [ ] For contract changes: access control, reentrancy and accounting consequences are described
- [ ] For EIP-712 changes: Solidity and Python sides updated together

## Reviews

A maintainer will review your PR as soon as they can. Please be patient and open to feedback. Small
PRs are reviewed much faster than large ones. If a PR sits without a response for a week, feel free
to leave a polite ping.

## Licensing

RiskLayer is released under the [MIT License](LICENSE). By submitting a contribution you agree that
it is licensed under the same terms.

## Questions

Open a GitHub Discussion or an issue. No question is too small.
