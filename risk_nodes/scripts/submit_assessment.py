
import json
import os
from pathlib import Path

from web3 import Web3
from eth_account import Account

RPC_URL = "http://127.0.0.1:8545"

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(__file__).resolve().parents[1] / "data"

MANAGER_ADDRESS = Web3.to_checksum_address(
    "0x959922bE3CAee4b8Cd9a407cc3ac1C251C2007B1"
)
ORACLE_ADDRESS = Web3.to_checksum_address(
    "0x68B1D87F95878fE05B998F19b66F4baba5De1aed"
)
VAULT_ADDRESS = Web3.to_checksum_address(
    "0x0B306BF915C4d645ff596e518fAf3F9669b97016"
)


def load_env():
    for path in [ROOT / ".env", DATA.parent / ".env"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def load_abi(contract_name):
    artifact = ROOT / "out" / f"{contract_name}.sol" / f"{contract_name}.json"
    if not artifact.exists():
        raise FileNotFoundError(f"Contract artifact not found: {artifact}")
    return json.loads(artifact.read_text())["abi"]


def main():
    load_env()

    private_key = os.getenv("DEPLOYER_PRIVATE_KEY")
    if not private_key:
        raise RuntimeError(
            "DEPLOYER_PRIVATE_KEY is missing. Set it in your environment or .env."
        )

    assessment_path = DATA / "onchain_assessment.json"
    if not assessment_path.exists():
        raise FileNotFoundError(f"Missing assessment file: {assessment_path}")

    result = json.loads(assessment_path.read_text())
    assessment = result["assessment"]
    signatures = result["signatures"]
    quorum = int(result["quorum"])

    intent_id = int(assessment["intentId"])
    signatures = [
        Web3.to_bytes(hexstr=s) if isinstance(s, str) else bytes(s)
        for s in signatures
    ]

    if len(signatures) < quorum:
        raise RuntimeError(
            f"Insufficient signatures: {len(signatures)} collected, {quorum} required."
        )

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to Anvil at {RPC_URL}")

    account = Account.from_key(private_key)
    sender = account.address

    manager = w3.eth.contract(
        address=MANAGER_ADDRESS,
        abi=load_abi("IntentManager"),
    )
    oracle = w3.eth.contract(
        address=ORACLE_ADDRESS,
        abi=load_abi("RiskOracle"),
    )
    vault = w3.eth.contract(
        address=VAULT_ADDRESS,
        abi=load_abi("LiquidityVault"),
    )

    # Read the existing intent. This script deliberately does NOT create one.
    intent = manager.functions.getIntent(intent_id).call()

    # Intent struct: id, taker, provider, amount, expiry, status
    onchain_taker = Web3.to_checksum_address(intent[1])
    onchain_provider = Web3.to_checksum_address(intent[2])
    onchain_amount = int(intent[3])
    onchain_status = int(intent[5])

    if onchain_status != 1:
        raise RuntimeError(
            f"Intent {intent_id} is not Open (status={onchain_status})."
        )

    if oracle.functions.assessmentSubmitted(intent_id).call():
        print(f"Assessment for intent {intent_id} is already recorded.")
        return

    # Ensure the signed assessment belongs to this exact on-chain intent.
    if Web3.to_checksum_address(assessment["taker"]) != onchain_taker:
        raise RuntimeError("Assessment taker does not match the on-chain intent.")

    if Web3.to_checksum_address(assessment["provider"]) != onchain_provider:
        raise RuntimeError("Assessment provider does not match the on-chain intent.")

    if int(assessment["amount"]) != onchain_amount:
        raise RuntimeError("Assessment amount does not match the on-chain intent.")

    approved = bool(assessment["approved"])
    risk_score = int(assessment["riskScoreBps"])
    max_amount = int(assessment["maxAmount"])
    spread = int(assessment["spreadBps"])
    collateral = int(assessment["collateralBps"])
    valid_until = int(assessment["validUntil"])

    print(f"Submitting assessment for existing intent {intent_id}")
    print(f"Collected signatures: {len(signatures)}")
    print(f"Required quorum: {quorum}")
    print(f"Decision: {'APPROVE' if approved else 'REJECT'}")

    tx = oracle.functions.submitAssessment(
        intent_id,
        approved,
        risk_score,
        max_amount,
        spread,
        collateral,
        valid_until,
        signatures,
    ).build_transaction({
        "from": sender,
        "nonce": w3.eth.get_transaction_count(sender),
        "chainId": w3.eth.chain_id,
        "gas": 1_500_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed = account.sign_transaction(tx)
    raw_tx = getattr(signed, "raw_transaction", None)
    if raw_tx is None:
        raw_tx = signed.rawTransaction

    tx_hash = w3.eth.send_raw_transaction(raw_tx)
    print("Transaction:", tx_hash.hex())

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError("Assessment transaction reverted.")

    # Verify the actual on-chain result.
    updated = manager.functions.getIntent(intent_id).call()
    recorded = oracle.functions.assessmentSubmitted(intent_id).call()
    reserved = vault.functions.reserved(onchain_provider).call()

    statuses = ["None", "Open", "Approved", "Rejected", "Cancelled", "Expired"]

    print("\n========== ASSESSMENT VERIFIED ==========")
    print("Intent ID:", intent_id)
    print("Status:", statuses[int(updated[5])])
    print("Assessment recorded:", recorded)
    print("Provider reserved:", reserved)
    print("Gas used:", receipt.gasUsed)


if __name__ == "__main__":
    main()

