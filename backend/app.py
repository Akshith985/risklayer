import json
import os
from pathlib import Path
from typing import Any

import sys
import time

from pydantic import BaseModel, Field

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from web3 import Web3


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(Path(__file__).resolve().parent / ".env")

RISK_NODES_DIR = ROOT / "risk_nodes"

if str(RISK_NODES_DIR) not in sys.path:
    sys.path.insert(0, str(RISK_NODES_DIR))

load_dotenv(RISK_NODES_DIR / ".env")

from nodes.aggregator import collect_assessments

RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")
CHAIN_ID = int(os.getenv("CHAIN_ID", "31337"))

ADDRESSES = {
    "usdc": os.getenv("USDC_ADDRESS"),
    "vault": os.getenv("VAULT_ADDRESS"),
    "manager": os.getenv("MANAGER_ADDRESS"),
    "oracle": os.getenv("ORACLE_ADDRESS"),
}

ARTIFACTS = {
    "usdc": ROOT / "out" / "MockUSDC.sol" / "MockUSDC.json",
    "vault": ROOT / "out" / "LiquidityVault.sol" / "LiquidityVault.json",
    "manager": ROOT / "out" / "IntentManager.sol" / "IntentManager.json",
    "oracle": ROOT / "out" / "RiskOracle.sol" / "RiskOracle.json",
}

STATUS_NAMES = [
    "None",
    "Open",
    "Approved",
    "Rejected",
    "Cancelled",
    "Expired",
]

app = FastAPI(
    title="RiskLayer API",
    description="Local API for the RiskLayer protocol",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 5}))


def load_contract(name: str):
    address = ADDRESSES[name]
    artifact_path = ARTIFACTS[name]

    if not address:
        raise RuntimeError(f"Missing {name} contract address")

    if not artifact_path.exists():
        raise RuntimeError(f"Missing contract artifact: {artifact_path}")

    with artifact_path.open() as file:
        artifact = json.load(file)

    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=artifact["abi"],
    )


def get_contracts():
    return {
        name: load_contract(name)
        for name in ADDRESSES
    }


def require_connection():
    if not w3.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Anvil. Start your local blockchain.",
        )

    if w3.eth.chain_id != CHAIN_ID:
        raise HTTPException(
            status_code=503,
            detail=f"Wrong chain. Expected {CHAIN_ID}, got {w3.eth.chain_id}",
        )


def get_decimals(usdc) -> int:
    return usdc.functions.decimals().call()


def format_amount(amount: int, decimals: int) -> float:
    return amount / (10 ** decimals)


def read_intent(manager, intent_id: int) -> dict[str, Any]:
    try:
        intent = manager.functions.getIntent(intent_id).call()
    except Exception:
        raise HTTPException(
            status_code=404,
            detail=f"Intent {intent_id} not found",
        )

    return {
        "id": intent[0],
        "taker": intent[1],
        "provider": intent[2],
        "amount_raw": intent[3],
        "expiry": intent[4],
        "status_id": intent[5],
        "status": STATUS_NAMES[int(intent[5])],
    }


@app.get("/")
def root():
    return {
        "name": "RiskLayer API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    require_connection()

    return {
        "status": "healthy",
        "blockchain": "connected",
        "chain_id": w3.eth.chain_id,
        "block_number": w3.eth.block_number,
    }


@app.get("/api/config")
def config():
    require_connection()

    return {
        "chain_id": CHAIN_ID,
        "rpc_url": RPC_URL,
        "contracts": ADDRESSES,
    }


@app.get("/api/abis")
def abis():
    result = {}

    for name, path in ARTIFACTS.items():
        if not path.exists():
            raise HTTPException(
                status_code=500,
                detail=f"Missing artifact for {name}",
            )

        with path.open() as file:
            result[name] = json.load(file)["abi"]

    return result


@app.get("/api/dashboard")
def dashboard():
    require_connection()
    contracts = get_contracts()

    usdc = contracts["usdc"]
    vault = contracts["vault"]
    manager = contracts["manager"]
    oracle = contracts["oracle"]

    decimals = get_decimals(usdc)

    total_deposits = vault.functions.totalDeposits().call()
    next_id = manager.functions.nextIntentId().call()

    intents = []
    providers = set()

    for intent_id in range(1, next_id):
        try:
            intent = read_intent(manager, intent_id)
            intents.append(intent)
            providers.add(intent["provider"])
        except HTTPException:
            continue

    status_counts = {
        status: 0
        for status in STATUS_NAMES
    }

    for intent in intents:
        status_counts[intent["status"]] += 1

    total_reserved = sum(
        vault.functions.reserved(provider).call()
        for provider in providers
    )

    return {
        "chain_id": CHAIN_ID,
        "block_number": w3.eth.block_number,
        "token_decimals": decimals,
        "total_deposits": format_amount(total_deposits, decimals),
        "total_deposits_raw": str(total_deposits),
        "total_reserved": format_amount(total_reserved, decimals),
        "total_reserved_raw": str(total_reserved),
        "available_liquidity": format_amount(
            total_deposits - total_reserved,
            decimals,
        ),
        "intent_count": len(intents),
        "status_counts": status_counts,
        "quorum": oracle.functions.quorum().call(),
        "intents": [
            {
                **intent,
                "amount": format_amount(
                    intent["amount_raw"],
                    decimals,
                ),
                "amount_raw": str(intent["amount_raw"]),
            }
            for intent in intents
        ],
    }


@app.get("/api/intents")
def list_intents():
    require_connection()

    contracts = get_contracts()
    manager = contracts["manager"]
    decimals = get_decimals(contracts["usdc"])

    next_id = manager.functions.nextIntentId().call()
    results = []

    for intent_id in range(1, next_id):
        try:
            intent = read_intent(manager, intent_id)
            intent["amount"] = format_amount(
                intent["amount_raw"],
                decimals,
            )
            intent["amount_raw"] = str(intent["amount_raw"])
            results.append(intent)
        except HTTPException:
            continue

    return {"intents": results}


@app.get("/api/intents/{intent_id}")
def get_intent(intent_id: int):
    require_connection()

    contracts = get_contracts()
    intent = read_intent(contracts["manager"], intent_id)

    decimals = get_decimals(contracts["usdc"])
    oracle = contracts["oracle"]

    submitted = oracle.functions.assessmentSubmitted(
        intent_id
    ).call()

    assessment = None

    if submitted:
        data = oracle.functions.getAssessment(intent_id).call()

        assessment = {
            "approved": data[0],
            "risk_score_bps": data[1],
            "max_amount_raw": str(data[2]),
            "spread_bps": data[3],
            "collateral_bps": data[4],
            "valid_until": data[5],
            "signatures": data[6],
        }

        assessment["max_amount"] = format_amount(
            data[2],
            decimals,
        )

    intent["amount"] = format_amount(
        intent["amount_raw"],
        decimals,
    )
    intent["amount_raw"] = str(intent["amount_raw"])

    return {
        "intent": intent,
        "assessment_submitted": submitted,
        "assessment": assessment,
    }


@app.get("/api/providers/{address}")
def provider_details(address: str):
    require_connection()

    if not Web3.is_address(address):
        raise HTTPException(
            status_code=400,
            detail="Invalid Ethereum address",
        )

    address = Web3.to_checksum_address(address)

    contracts = get_contracts()
    vault = contracts["vault"]
    usdc = contracts["usdc"]

    decimals = get_decimals(usdc)

    deposited = vault.functions.deposits(address).call()
    reserved = vault.functions.reserved(address).call()
    available = vault.functions.availableDeposit(address).call()

    return {
        "address": address,
        "deposited": format_amount(deposited, decimals),
        "reserved": format_amount(reserved, decimals),
        "available": format_amount(available, decimals),
        "deposited_raw": str(deposited),
        "reserved_raw": str(reserved),
        "available_raw": str(available),
        "wallet_balance": format_amount(
            usdc.functions.balanceOf(address).call(),
            decimals,
        ),
    }

class RiskFeaturesRequest(BaseModel):
    provider_reversal_rate: float = Field(ge=0, le=1)
    taker_dispute_rate: float = Field(ge=0, le=1)
    account_age_days: int = Field(ge=0)
    transactions_last_hour: int = Field(ge=0)
    payment_method_risk: float = Field(ge=0, le=1)


@app.post("/api/intents/{intent_id}/assess")
def assess_intent(intent_id: int, request: RiskFeaturesRequest):
    require_connection()

    contracts = get_contracts()
    manager = contracts["manager"]
    vault = contracts["vault"]
    oracle = contracts["oracle"]

    try:
        intent = manager.functions.getIntent(intent_id).call()
    except Exception:
        raise HTTPException(status_code=404, detail="Intent not found")

    # IntentStatus.Open == 1
    if int(intent[5]) != 1:
        raise HTTPException(
            status_code=409,
            detail="Only open intents can be assessed",
        )

    if oracle.functions.assessmentSubmitted(intent_id).call():
        raise HTTPException(
            status_code=409,
            detail="An assessment has already been submitted",
        )

    taker = Web3.to_checksum_address(intent[1])
    provider = Web3.to_checksum_address(intent[2])
    amount = int(intent[3])
    expiry = int(intent[4])

    now = int(time.time())
    valid_until = min(expiry, now + 300)

    if valid_until <= now:
        raise HTTPException(
            status_code=409,
            detail="Intent is expired or too close to expiry",
        )

    # Use on-chain provider liquidity, not a client-supplied value.
    deposited = int(vault.functions.deposits(provider).call())

    # The current intent is already reserved, so include its amount
    # when estimating the provider's committed liquidity.
    reserved = int(vault.functions.reserved(provider).call())
    provider_capacity = max(deposited - reserved + amount, amount)

    nonce = int(oracle.functions.assessmentNonce(intent_id).call())

    payload = {
        "intent": {
            "chain_id": int(w3.eth.chain_id),
            "oracle_address": Web3.to_checksum_address(oracle.address),
            "intent_id": intent_id,
            "taker": taker,
            "provider": provider,
            "amount": amount,
            "valid_until": valid_until,
            "nonce": nonce,
        },
        "features": {
            "amount": amount,
            "provider_capacity": provider_capacity,
            "provider_reversal_rate": request.provider_reversal_rate,
            "taker_dispute_rate": request.taker_dispute_rate,
            "account_age_days": request.account_age_days,
            "transactions_last_hour": request.transactions_last_hour,
            "payment_method_risk": request.payment_method_risk,
        },
    }

    try:
        result = collect_assessments(payload, quorum=3)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Risk assessment failed: {str(exc)}",
        )

    assessment = result["assessment"]

    return {
        "intent_id": intent_id,
        "assessment": assessment,
        "digest": result["digest"],
        "signatures": result["signatures"],
        "signers": result["signers"],
        "quorum": result["quorum"],
        "collected": result["collected"],
        "node_results": result["node_results"],
        "valid_until": valid_until,
    }
