
import json
from pathlib import Path

from web3 import Web3

ROOT = Path(__file__).resolve().parents[2]

RPC_URL = "http://127.0.0.1:8545"

ADDRESSES = {
    "token": "0x9A676e781A523b5d0C0e43731313A708CB607508",
    "vault": "0x0B306BF915C4d645ff596e518fAf3F9669b97016",
    "manager": "0x959922bE3CAee4b8Cd9a407cc3ac1C251C2007B1",
    "oracle": "0x68B1D87F95878fE05B998F19b66F4baba5De1aed",
}


def load_contract(w3, address, artifact_path):
    with open(artifact_path, "r", encoding="utf-8") as f:
        artifact = json.load(f)

    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=artifact["abi"],
    )


def send_and_confirm(w3, tx_hash):
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.status != 1:
        raise RuntimeError(f"Transaction failed: {tx_hash.hex()}")

    print("Confirmed:", tx_hash.hex())
    return receipt


def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        raise RuntimeError("Cannot connect to Anvil.")

    if w3.eth.chain_id != 31337:
        raise RuntimeError("Expected Anvil chain ID 31337.")

    accounts = w3.eth.accounts
    deployer = accounts[0]
    taker = accounts[1]
    provider = accounts[2]

    artifacts = ROOT / "out"

    token = load_contract(
        w3, ADDRESSES["token"],
        artifacts / "MockUSDC.sol" / "MockUSDC.json"
    )
    vault = load_contract(
        w3, ADDRESSES["vault"],
        artifacts / "LiquidityVault.sol" / "LiquidityVault.json"
    )
    manager = load_contract(
        w3, ADDRESSES["manager"],
        artifacts / "IntentManager.sol" / "IntentManager.json"
    )
    oracle = load_contract(
        w3, ADDRESSES["oracle"],
        artifacts / "RiskOracle.sol" / "RiskOracle.json"
    )

    # USDC uses six decimal places.
    deposit_amount = 1_000 * 10**6
    intent_amount = 200 * 10**6

    print("\n=== ACCOUNTS ===")
    print("Deployer:", deployer)
    print("Taker:", taker)
    print("Provider:", provider)

    # Mint test USDC to the provider.
    tx = token.functions.mint(
        provider, deposit_amount
    ).transact({"from": deployer})
    send_and_confirm(w3, tx)

    # Approve the vault to transfer provider funds.
    tx = token.functions.approve(
        ADDRESSES["vault"], deposit_amount
    ).transact({"from": provider})
    send_and_confirm(w3, tx)

    # Deposit provider liquidity.
    tx = vault.functions.deposit(
        deposit_amount
    ).transact({"from": provider})
    send_and_confirm(w3, tx)

    print("\n=== PROVIDER LIQUIDITY ===")
    print("Deposited:", vault.functions.deposits(provider).call())
    print("Available:", vault.functions.availableDeposit(provider).call())

    # Read the next intent ID before creating the intent.
    intent_id = manager.functions.nextIntentId().call()

    latest_block = w3.eth.get_block("latest")
    intent_expiry = latest_block["timestamp"] + 3600

    # Create a real on-chain intent.
    tx = manager.functions.createIntent(
        provider,
        intent_amount,
        intent_expiry,
    ).transact({"from": taker})

    receipt = send_and_confirm(w3, tx)

    # Read the authoritative intent from the contract.
    intent = manager.functions.getIntent(intent_id).call()
    nonce = oracle.functions.assessmentNonce(intent_id).call()

    if int(intent[5]) != 1:
        raise RuntimeError("New intent is not in Open status.")

    # Build the payload consumed by the risk nodes.
    payload = {
        "chain_id": w3.eth.chain_id,
        "oracle_address": ADDRESSES["oracle"],
        "intent": {
            "intent_id": int(intent[0]),
            "taker": intent[1],
            "provider": intent[2],
            "amount": int(intent[3]),
            "valid_until": int(intent[4]),
            "nonce": int(nonce),
        },
        "features": {
            "amount": int(intent[3]),
            "provider_capacity": int(deposit_amount),
            "provider_reversal_rate": 0.02,
            "taker_dispute_rate": 0.01,
            "account_age_days": 180,
            "transactions_last_hour": 3,
            "payment_method_risk": 0.1,
        },
    }

    output_path = ROOT / "risk_nodes" / "data" / "onchain_intent.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4)

    print("\n=== ON-CHAIN INTENT CREATED ===")
    print("Intent ID:", intent_id)
    print("Taker:", intent[1])
    print("Provider:", intent[2])
    print("Amount:", int(intent[3]))
    print("Expiry:", int(intent[4]))
    print("Status:", int(intent[5]))
    print("Assessment nonce:", int(nonce))
    print("Reserved:", vault.functions.reserved(provider).call())
    print("Transaction:", receipt.transactionHash.hex())
    print("Risk input saved:", output_path)


if __name__ == "__main__":
    main()
