
import argparse
import json
from pathlib import Path

from config import get_node_key
from nodes.node import process_node
from nodes.signer import recover_signer


NODE_IDS = ["node1", "node2", "node3", "node4"]


def collect_assessments(
    payload: dict,
    quorum: int = 3,
) -> dict:
    if quorum < 1 or quorum > len(NODE_IDS):
        raise ValueError("Quorum must be between 1 and 4")

    intent = payload["intent"]
    chain_id = int(intent["chain_id"])
    oracle_address = intent["oracle_address"]

    results = []
    errors = []

    for node_id in NODE_IDS:
        try:
            private_key = get_node_key(node_id)

            result = process_node(
                node_id=node_id,
                payload=payload,
                private_key=private_key,
            )

            results.append(result)

        except Exception as exc:
            errors.append({
                "node_id": node_id,
                "error": f"{type(exc).__name__}: {exc}",
            })

    if len(results) < quorum:
        error_details = "; ".join(
            f"{item['node_id']}: {item['error']}"
            for item in errors
        )

        raise RuntimeError(
            f"Quorum not reached: {len(results)}/{quorum} signatures. "
            f"Node errors: {error_details}"
        )

    reference_assessment = results[0]["assessment"]
    reference_hash = results[0]["message_hash"]

    unique_signers = set()
    valid_results = []

    for result in results:
        if result["assessment"] != reference_assessment:
            raise RuntimeError(
                f"{result['node_id']} produced a different assessment"
            )

        if result["message_hash"].lower() != reference_hash.lower():
            raise RuntimeError(
                f"{result['node_id']} signed a different digest"
            )

        recovered = recover_signer(
            chain_id,
            oracle_address,
            result["assessment"],
            result["signature"],
        )

        if recovered.lower() != result["signer"].lower():
            raise RuntimeError(
                f"Invalid signature from {result['node_id']}"
            )

        signer = recovered.lower()

        if signer in unique_signers:
            raise RuntimeError(
                f"Duplicate signer detected: {recovered}"
            )

        unique_signers.add(signer)
        valid_results.append(result)

    if len(valid_results) < quorum:
        raise RuntimeError("Insufficient valid signatures")

    return {
        "assessment": reference_assessment,
        "digest": reference_hash,
        "message_hash": reference_hash,
        "signatures": [
            result["signature"] for result in valid_results
        ],
        "signers": [
            result["signer"] for result in valid_results
        ],
        "node_results": [
            {
                "node_id": result["node_id"],
                "signer": result["signer"],
                "risk_reasons": result["risk_reasons"],
            }
            for result in valid_results
        ],
        "quorum": quorum,
        "collected": len(valid_results),
        "node_errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="RiskLayer 3-of-4 signature aggregator"
    )

    parser.add_argument(
        "--input",
        default="data/node_input.json",
    )

    parser.add_argument(
        "--quorum",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--output",
        default="data/aggregated_assessment.json",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    result = collect_assessments(
        payload=payload,
        quorum=args.quorum,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=4)

    print("\n========== RISKLAYER AGGREGATOR ==========")
    print("Assessment digest:", result["digest"])
    print("Collected signatures:", result["collected"])
    print("Required quorum:", result["quorum"])

    for signer in result["signers"]:
        print("Verified signer:", signer)

    print("Approved:", result["assessment"]["approved"])
    print("Risk score:", result["assessment"]["riskScoreBps"])
    print("Output:", output_path)
    print("\nSUCCESS: Signature quorum reached.")


if __name__ == "__main__":
    main()



