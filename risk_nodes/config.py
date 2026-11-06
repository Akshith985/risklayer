
import os
from pathlib import Path
from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_FILE)

NODE_KEYS = {
    "node1": os.getenv("NODE_1_PRIVATE_KEY"),
    "node2": os.getenv("NODE_2_PRIVATE_KEY"),
    "node3": os.getenv("NODE_3_PRIVATE_KEY"),
    "node4": os.getenv("NODE_4_PRIVATE_KEY"),
}


def get_node_key(node_id: str) -> str:
    key = NODE_KEYS.get(node_id)

    if not key:
        raise RuntimeError(
            f"Private key for {node_id} is not configured"
        )

    return key

