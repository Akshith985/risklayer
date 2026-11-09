# Security Policy

## Project status

RiskLayer is **experimental, unaudited software intended for testnets only**. Do not deploy it with, or
rely on it to protect, real funds. The contracts have not undergone a formal security review.

## Supported versions

There are no tagged releases yet. Security fixes are made against the `master` branch only.

| Version | Supported |
| --- | --- |
| `master` | Yes |
| Anything else | No |

## Reporting a vulnerability

**Please do not open a public issue, pull request or discussion for security problems.**

Report privately using either of these:

1. **GitHub private vulnerability reporting** (preferred): go to the repository's **Security** tab and
   choose **Report a vulnerability**.
2. **Email:** `<security-contact-email>`

Please include as much of the following as you can:

- A description of the issue and its impact
- The affected contract, file or endpoint, and commit hash
- Steps to reproduce, ideally a Forge test or script that demonstrates it
- A suggested fix, if you have one

## What to expect

These are targets, not guarantees, since this is a small project:

- Acknowledgement of your report within about 3 business days
- An initial assessment within about 7 days
- Coordinated disclosure: we ask that you give us reasonable time to fix the issue before publishing
  details, and we will credit you in the fix unless you prefer to stay anonymous

## Scope

**In scope**

- `src/LiquidityVault.sol`, `src/IntentManager.sol`, `src/RiskOracle.sol`
- Signature handling: EIP-712 digest construction, replay, malleability and quorum logic
- Fund accounting: deposits, reservations, releases, withdrawals
- Access control and configuration (one-time wiring, node set, quorum)
- The backend API and the risk node signing code, where the issue could affect on-chain safety

**Out of scope**

- `MockUSDC` (unrestricted minting is intentional for testing)
- Issues already listed under *Known limitations* in the [README](README.md), including the
  single-process risk nodes, user-supplied risk features, and the missing settlement step
- Findings that require a compromised private key or a compromised host
- Denial of service through spam, rate limiting, or testnet infrastructure outages
- Vulnerabilities in third-party dependencies with no demonstrated impact on RiskLayer (report those
  upstream)
- Social engineering, physical attacks, and issues in wallets or browsers

## Safe harbor

We will not pursue action against anyone who researches and reports vulnerabilities in good faith,
follows this policy, avoids privacy violations and service disruption, and only tests against local
chains or testnets with their own accounts and funds.

## Bounties

There is currently **no bug bounty program**. We are grateful for responsible reports and will give
public credit.

## Key hygiene reminder

Never commit private keys, mnemonics or `.env` files. If you find a leaked credential in this
repository's history, report it using the channels above so it can be rotated and scrubbed.
