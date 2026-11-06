
from eth_account import Account
from eth_account.messages import encode_typed_data
from web3 import Web3


DOMAIN_NAME = "RiskLayer RiskOracle"
DOMAIN_VERSION = "1"

EIP712_TYPES = {
    "RiskAssessment": [
        {"name": "intentId", "type": "uint256"},
        {"name": "taker", "type": "address"},
        {"name": "provider", "type": "address"},
        {"name": "amount", "type": "uint256"},
        {"name": "approved", "type": "bool"},
        {"name": "riskScoreBps", "type": "uint16"},
        {"name": "maxAmount", "type": "uint256"},
        {"name": "spreadBps", "type": "uint16"},
        {"name": "collateralBps", "type": "uint16"},
        {"name": "validUntil", "type": "uint64"},
        {"name": "nonce", "type": "uint64"},
    ]
}


def build_typed_data(
    chain_id: int,
    verifying_contract: str,
    assessment: dict
) -> dict:

    required_fields = [
        "intentId",
        "taker",
        "provider",
        "amount",
        "approved",
        "riskScoreBps",
        "maxAmount",
        "spreadBps",
        "collateralBps",
        "validUntil",
        "nonce",
    ]

    for field in required_fields:
        if field not in assessment:
            raise ValueError(f"Missing assessment field: {field}")

    if chain_id <= 0:
        raise ValueError("Invalid chain ID")

    if not Web3.is_address(verifying_contract):
        raise ValueError("Invalid verifying contract address")

    if not Web3.is_address(assessment["taker"]):
        raise ValueError("Invalid taker address")

    if not Web3.is_address(assessment["provider"]):
        raise ValueError("Invalid provider address")

    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            **EIP712_TYPES,
        },
        "primaryType": "RiskAssessment",
        "domain": {
            "name": DOMAIN_NAME,
            "version": DOMAIN_VERSION,
            "chainId": chain_id,
            "verifyingContract": Web3.to_checksum_address(
                verifying_contract
            ),
        },
        "message": {
            field: assessment[field]
            for field in required_fields
        },
    }


def sign_assessment(
    private_key: str,
    chain_id: int,
    verifying_contract: str,
    assessment: dict
) -> dict:

    typed_data = build_typed_data(
        chain_id,
        verifying_contract,
        assessment
    )

    account = Account.from_key(private_key)

    signable_message = encode_typed_data(
        full_message=typed_data
    )

    signed = Account.sign_message(
        signable_message,
        private_key=private_key
    )

    return {
        "signer": account.address,
        "signature": signed.signature.hex(),
        "message_hash": signed.message_hash.hex(),
    }


def recover_signer(
    chain_id: int,
    verifying_contract: str,
    assessment: dict,
    signature: str
) -> str:

    typed_data = build_typed_data(
        chain_id,
        verifying_contract,
        assessment
    )

    signable_message = encode_typed_data(
        full_message=typed_data
    )

    return Account.recover_message(
        signable_message,
        signature=signature
    )
