
from eth_account import Account

from nodes.signer import (
    sign_assessment,
    recover_signer
)


CHAIN_ID = 31337

ORACLE_ADDRESS = "0x1111111111111111111111111111111111111111"

ASSESSMENT = {
    "intentId": 1,
    "taker": "0x2222222222222222222222222222222222222222",
    "provider": "0x3333333333333333333333333333333333333333",
    "amount": 200_000000,
    "approved": True,
    "riskScoreBps": 1200,
    "maxAmount": 500_000000,
    "spreadBps": 110,
    "collateralBps": 1700,
    "validUntil": 1900000000,
    "nonce": 0,
}


def test_signature_recovers_correct_signer():
    account = Account.create()

    result = sign_assessment(
        account.key.hex(),
        CHAIN_ID,
        ORACLE_ADDRESS,
        ASSESSMENT
    )

    recovered = recover_signer(
        CHAIN_ID,
        ORACLE_ADDRESS,
        ASSESSMENT,
        result["signature"]
    )

    assert recovered.lower() == account.address.lower()


def test_modified_assessment_changes_signer():
    account = Account.create()

    result = sign_assessment(
        account.key.hex(),
        CHAIN_ID,
        ORACLE_ADDRESS,
        ASSESSMENT
    )

    modified = dict(ASSESSMENT)
    modified["amount"] += 1

    recovered = recover_signer(
        CHAIN_ID,
        ORACLE_ADDRESS,
        modified,
        result["signature"]
    )

    assert recovered.lower() != account.address.lower()


def test_different_chain_id_changes_signer():
    account = Account.create()

    result = sign_assessment(
        account.key.hex(),
        CHAIN_ID,
        ORACLE_ADDRESS,
        ASSESSMENT
    )

    recovered = recover_signer(
        CHAIN_ID + 1,
        ORACLE_ADDRESS,
        ASSESSMENT,
        result["signature"]
    )

    assert recovered.lower() != account.address.lower()


def test_different_contract_changes_signer():
    account = Account.create()

    result = sign_assessment(
        account.key.hex(),
        CHAIN_ID,
        ORACLE_ADDRESS,
        ASSESSMENT
    )

    different_oracle = (
        "0x4444444444444444444444444444444444444444"
    )

    recovered = recover_signer(
        CHAIN_ID,
        different_oracle,
        ASSESSMENT,
        result["signature"]
    )

    assert recovered.lower() != account.address.lower()
