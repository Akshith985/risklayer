
import json
from pathlib import Path
from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"

MANAGER_ADDRESS = Web3.to_checksum_address(
    "0x959922bE3CAee4b8Cd9a407cc3ac1C251C2007B1"
)

VAULT_ADDRESS = Web3.to_checksum_address(
    "0x0B306BF915C4d645ff596e518fAf3F9669b97016"
)

ORACLE_ADDRESS = Web3.to_checksum_address(
    "0x68B1D87F95878fE05B998F19b66F4baba5De1aed"
)

BASE = Path(__file__).resolve().parents[1]

with open(BASE / "data/onchain_intent.json") as f:
    data = json.load(f)

intent_id = data["intent"]["intent_id"]
provider = Web3.to_checksum_address(data["intent"]["provider"])

w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise SystemExit("Cannot connect to Anvil")

def load_abi(contract_name):
    path = BASE.parent / "out" / f"{contract_name}.sol" / f"{contract_name}.json"
    with open(path) as f:
        return json.load(f)["abi"]

manager = w3.eth.contract(
    address=MANAGER_ADDRESS,
    abi=load_abi("IntentManager")
)

vault = w3.eth.contract(
    address=VAULT_ADDRESS,
    abi=load_abi("LiquidityVault")
)

oracle = w3.eth.contract(
    address=ORACLE_ADDRESS,
    abi=load_abi("RiskOracle")
)

intent = manager.functions.getIntent(intent_id).call()
reserved = vault.functions.reserved(provider).call()
assessment_recorded = oracle.functions.assessmentSubmitted(intent_id).call()

# Intent struct order:
# taker, provider, amount, expiry, status
status = intent[4]

status_names = {
    0: "None",
    1: "Open",
    2: "Approved",
    3: "Rejected",
    4: "Cancelled",
    5: "Expired",
}

print("\n========== RISKLAYER LIFECYCLE VERIFICATION ==========")
print("Intent ID:", intent_id)
print("Intent status:", status_names.get(status, f"Unknown ({status})"))
print("Intent amount:", intent[2])
print("Provider reserved liquidity:", reserved)
print("Assessment recorded:", assessment_recorded)

print("\n========== EXPECTED STATE ==========")
print("Approved:", status == 2)
print("200 USDC reserved:", reserved >= 200_000_000)
print("Assessment recorded:", assessment_recorded)

if status == 2 and reserved >= 200_000_000 and assessment_recorded:
    print("\nSUCCESS: Approved lifecycle verified.")
else:
    print("\nCHECK REQUIRED: State differs from expected values.")
