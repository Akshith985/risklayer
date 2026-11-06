
import argparse
import json
from pathlib import Path

from config import get_node_key
from nodes.risk_engine import TransactionFeatures, evaluate_risk
from nodes.signer import sign_assessment


def process_node(node_id: str, payload: dict, private_key: str) -> dict:
    """
    Independently evaluate a transaction and sign its risk assessment.
    """

    intent = payload["intent"]

    features = TransactionFeatures(**payload["features"])

    if int(features.amount) != int(intent["amount"]):
        raise ValueError(
            "Feature amount must match the on-chain intent amount"
        )

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

    signature = sign_assessment(
        private_key=private_key,
        chain_id=int(intent["chain_id"]),
        verifying_contract=payload["intent"]["oracle_address"],
        assessment=assessment,
    )

    return {
        "node_id": node_id,
        "signer": signature["signer"],
        "assessment": assessment,
        "signature": signature["signature"],
        "message_hash": signature["message_hash"],
        "risk_reasons": risk.reasons,
    }


def main():
    parser = argparse.ArgumentParser(
        description="RiskLayer independent risk node"
    )

    parser.add_argument(
        "--node",
        required=True,
        choices=["node1", "node2", "node3", "node4"],
    )

    parser.add_argument(
        "--input",
        default="data/node_input.json",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    private_key = get_node_key(args.node)

    result = process_node(
        node_id=args.node,
        payload=payload,
        private_key=private_key,
    )

    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()

