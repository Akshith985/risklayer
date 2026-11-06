
import json
import sys
from pathlib import Path

# risk_nodes directory
ROOT = Path(__file__).resolve().parents[1]

# Add risk_nodes to Python's module search path
sys.path.insert(0, str(ROOT))

from web3 import Web3

from config import get_node_key
from nodes.risk_engine import TransactionFeatures, evaluate_risk
from nodes.signer import sign_assessment, recover_signer

ORACLE_ADDRESS = "0x68B1D87F95878fE05B998F19b66F4baba5De1aed"
CHAIN_ID = 31337
RPC_URL = "http://127.0.0.1:8545"



def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    if not w3.is_connected():
        raise RuntimeError("Cannot connect to Anvil. Is it running?")

    if w3.eth.chain_id != CHAIN_ID:
        raise RuntimeError(f"Unexpected chain ID: {w3.eth.chain_id}")

    # Load deployed RiskOracle ABI.
    artifact_path = ROOT.parent / "out" / "RiskOracle.sol" / "RiskOracle.json"

    with artifact_path.open("r", encoding="utf-8") as file:
        artifact = json.load(file)

    oracle = w3.eth.contract(
        address=Web3.to_checksum_address(ORACLE_ADDRESS),
        abi=artifact["abi"],
    )

    # Load the sample transaction.
    input_path = ROOT / "data" / "node_input.json"

    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    intent = payload["intent"]
    features = TransactionFeatures(**payload["features"])
    risk = evaluate_risk(features)

    assessment = {
        "intentId": int(intent["intent_id"]),
        "taker": intent["taker"],
        "provider": intent["provider"],
        "amount": int(intent["amount"]),
        "approved": risk.approved,
        "riskScoreBps": risk.risk_score_bps,
        "maxAmount": risk.max_amount,
        "spreadBps": risk.spread_bps,
        "collateralBps": risk.collateral_bps,
        "validUntil": int(intent["valid_until"]),
        "nonce": int(intent["nonce"]),
    }

    # Sign using the actual local node1 identity.
    signed = sign_assessment(
        private_key=get_node_key("node1"),
        chain_id=CHAIN_ID,
        verifying_contract=ORACLE_ADDRESS,
        assessment=assessment,
    )

    # Ask Solidity to calculate the same EIP-712 digest.
    solidity_digest = oracle.functions.getDigest(
        assessment["intentId"],
        assessment["taker"],
        assessment["provider"],
        assessment["amount"],
        assessment["approved"],
        assessment["riskScoreBps"],
        assessment["maxAmount"],
        assessment["spreadBps"],
        assessment["collateralBps"],
        assessment["validUntil"],
        assessment["nonce"],
    ).call()

    solidity_hash = Web3.to_hex(solidity_digest)

    python_hash = str(signed["message_hash"])
    if not python_hash.startswith("0x"):
        python_hash = "0x" + python_hash

    print("\n========== EIP-712 COMPATIBILITY ==========")
    print("Python signer:", signed["signer"])
    print("Python digest:", python_hash)
    print("Solidity digest:", solidity_hash)

    recovered = recover_signer(
        CHAIN_ID,
        ORACLE_ADDRESS,
        assessment,
        signed["signature"],
    )

    print("Recovered signer:", recovered)

    if python_hash.lower() != solidity_hash.lower():
        raise RuntimeError("EIP-712 digest mismatch!")

    if recovered.lower() != signed["signer"].lower():
        raise RuntimeError("Signature recovery mismatch!")

    print("\nSUCCESS: Python and Solidity EIP-712 digests match.")
    print("SUCCESS: Node signature recovers correctly.")


if __name__ == "__main__":
    main()
