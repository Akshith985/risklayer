
import pytest

from eth_account import Account

from nodes.node import process_node
from nodes.signer import recover_signer


def sample_payload():
    return {
        "chain_id": 31337,
        "oracle_address": (
            "0x1111111111111111111111111111111111111111"
        ),
        "intent": {
            "intent_id": 1,
            "taker": "0x2222222222222222222222222222222222222222",
            "provider": "0x3333333333333333333333333333333333333333",
            "amount": 200_000000,
            "valid_until": 1900000000,
            "nonce": 0,
        },
        "features": {
            "amount": 200_000000,
            "provider_capacity": 1000_000000,
            "provider_reversal_rate": 0.02,
            "taker_dispute_rate": 0.01,
            "account_age_days": 180,
            "transactions_last_hour": 3,
            "payment_method_risk": 0.10,
        },
    }


def test_node_produces_valid_signature():
    account = Account.create()

    result = process_node(
        "node1",
        sample_payload(),
        account.key.hex(),
    )

    recovered = recover_signer(
        31337,
        sample_payload()["oracle_address"],
        result["assessment"],
        result["signature"],
    )

    assert recovered.lower() == account.address.lower()
    assert result["node_id"] == "node1"


def test_node_rejects_amount_mismatch():
    account = Account.create()
    payload = sample_payload()

    payload["features"]["amount"] = 300_000000

    with pytest.raises(ValueError):
        process_node(
            "node1",
            payload,
            account.key.hex(),
        )
