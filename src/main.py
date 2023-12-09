from .services.flashbots_service import FlashbotsService

from web3 import Web3, HTTPProvider
from web3.types import TxParams
from dotenv import dotenv_values
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from flashbots.flashbots import FlashbotsBundleResponse

from typing import Dict, Any, List

# Load environment variables from .env
env: Dict[str, Any] = dotenv_values(".env")

def main() -> None:
    # Create a web3 object with a standard json rpc provider, such as Infura, Alchemy, or your own node.
    w3 = Web3(HTTPProvider(env.get("HTTP_PROVIDER_URL")))

    # Load Flashbots relay URL
    bundle_relay_url: str = env.get("FLASHBOTS_BUNDLE_RELAY_URL")

    # Initialize flashbots service
    flashbots_service: FlashbotsService = FlashbotsService(
        w3 = w3,
        bundle_relay_url = bundle_relay_url
    )

    # Prepare transactions
    # Send to random address
    sender: LocalAccount = Account.from_key(env.get("WALLET_PRIVATE_KEY"))
    receiver: LocalAccount = Account.create()

    # Send to random address
    print(
        f"Sender account balance: {Web3.fromWei(w3.eth.get_balance(sender.address), 'ether')} ETH"
    )
    print(
        f"Receiver account balance: {Web3.fromWei(w3.eth.get_balance(receiver.address), 'ether')} ETH"
    )

    nonce = w3.eth.get_transaction_count(sender.address)
    tx1: TxParams = {
        "to": receiver.address,
        "value": Web3.toWei(0.001, "ether"),
        # "gasPrice": w3.eth.gas_price,
        "gas": 21000,
        "maxFeePerGas": Web3.toWei(200, "gwei"),
        "maxPriorityFeePerGas": Web3.toWei(50, "gwei"),
        "nonce": nonce,
        "chainId": int(env.get("CHAIN_ID")),
        "type": 2,
    }
    tx1_signed = sender.sign_transaction(tx1)

    tx2: TxParams = {
        "to": receiver.address,
        "value": Web3.toWei(0.001, "ether"),
        # "gasPrice": w3.eth.gas_price,
        "gas": 21000,
        "maxFeePerGas": Web3.toWei(200, "gwei"),
        "maxPriorityFeePerGas": Web3.toWei(50, "gwei"),
        "nonce": nonce + 1,
        "chainId": int(env.get("CHAIN_ID")),
        "type": 2,
    }

    bundle = [
        {"signed_transaction": tx1_signed.rawTransaction}
    ]

    # Send bundle
    print(
        f"Sending bundle: {bundle}"
    )

    send_result: FlashbotsBundleResponse = flashbots_service.send_bundle(
        bundle = bundle
    )

    print(send_result)
    # print(send_result.receipts())

    print(
        f"Sender account balance: {Web3.fromWei(w3.eth.get_balance(sender.address), 'ether')} ETH"
    )
    print(
        f"Receiver account balance: {Web3.fromWei(w3.eth.get_balance(receiver.address), 'ether')} ETH"
    )

if __name__ == "__main__":
    main()