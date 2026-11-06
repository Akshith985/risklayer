
from pathlib import Path
from eth_account import Account

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

NODE_NAMES = [
    "NODE_1_PRIVATE_KEY",
    "NODE_2_PRIVATE_KEY",
    "NODE_3_PRIVATE_KEY",
    "NODE_4_PRIVATE_KEY",
]


def main():
    if ENV_PATH.exists():
        existing = ENV_PATH.read_text(encoding="utf-8")
        for name in NODE_NAMES:
            for line in existing.splitlines():
                if line.startswith(name + "=") and line.split("=", 1)[1].strip():
                    raise RuntimeError(
                        f"{name} already exists. Refusing to overwrite keys."
                    )

    accounts = [Account.create() for _ in NODE_NAMES]

    env_lines = [
        f"{name}={account.key.hex()}"
        for name, account in zip(NODE_NAMES, accounts)
    ]

    existing_lines = []
    if ENV_PATH.exists():
        existing_lines = [
            line for line in ENV_PATH.read_text(encoding="utf-8").splitlines()
            if not any(line.startswith(name + "=") for name in NODE_NAMES)
        ]

    ENV_PATH.write_text(
        "\n".join(existing_lines + env_lines) + "\n",
        encoding="utf-8",
    )

    ENV_PATH.chmod(0o600)

    print("Generated four local node identities:\n")
    for index, account in enumerate(accounts, start=1):
        print(f"Node {index}: {account.address}")

    print("\nPrivate keys saved locally in .env.")
    print("Do not share or publish this file.")


if __name__ == "__main__":
    main()
