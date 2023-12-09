import pandas as pd
from web3 import Web3, HTTPProvider, AsyncHTTPProvider
from web3.eth import AsyncEth
from web3.types import _Hash32
from web3.datastructures import AttributeDict
from web3.exceptions import TransactionNotFound
from eth_typing.evm import Address, BlockNumber
from dotenv import dotenv_values
import asyncio

from typing import Dict, Any, List, Union
from hexbytes import HexBytes

# Load environment variables from .env
env: Dict[str, Any] = dotenv_values(".env")

# Create a web3 object with a standard json rpc provider, such as Infura, Alchemy, or your own node.
w3: Web3 = Web3(AsyncHTTPProvider(env.get("HTTP_PROVIDER_URL")), modules = {"eth": AsyncEth}, middlewares=[])

async def get_transaction_for_hash(tx_hash: _Hash32, delay: int = 0) -> Dict[str, Any]:
    try:
        transaction: Dict[str, Any] = dict(await w3.eth.get_transaction(tx_hash))
        await asyncio.sleep(delay = delay)
        for key in transaction:
            if isinstance(transaction[key], HexBytes):
                transaction[key] = transaction[key].hex()
        return transaction
    except TransactionNotFound:
        return None


def process_response(response: Union[HexBytes, Dict, AttributeDict, List]) -> Dict[str, Any]:
    if isinstance(response, HexBytes):
        response = response.hex()
    elif isinstance(response, (dict, AttributeDict)):
        response = dict(response)
        for key in response:
            if isinstance(response[key], (HexBytes, dict, AttributeDict, list)):
                response[key] = process_response(response[key])
    elif isinstance(response, list):
        for idx in range(len(response)): 
            if isinstance(response[idx], (HexBytes, dict, AttributeDict, list)):
                response[idx] = process_response(response[idx])
                    
    return response

async def get_transaction_receipt_for_hash(tx_hash: _Hash32, delay: int = 0) -> Dict[str, Any]:
    try:
        transaction_receipt: Dict[str, Any] = dict(await w3.eth.get_transaction_receipt(tx_hash))
        await asyncio.sleep(delay = delay)
        
        return process_response(transaction_receipt)
    except TransactionNotFound:
        return None


async def get_transaction_data(raw_data: pd.DataFrame, delay: int = 0) -> pd.DataFrame:
    transaction_data = await asyncio.gather(
        *[
            get_transaction_for_hash(tx_hash, delay = delay) for tx_hash in raw_data["tx"]
        ]
    )

    return pd.DataFrame(filter(lambda x: x is not None, transaction_data))

def fetch_transaction_data_from_raw():
    ankr_data: pd.DataFrame = pd.read_csv("data/ankr_data.csv").query(
        "level == 'info'"
    )[["time", "tx"]].reset_index(drop = True)

    ankr_data_exclusive: pd.DataFrame = asyncio.get_event_loop().run_until_complete(get_transaction_data(ankr_data)).sort_values(
        by = "blockNumber"
    ).reset_index(drop = True)

    ankr_data_exclusive.to_csv("data/ankr_transaction_data.csv", index = False)


def fetch_transaction_receipt_from_raw():
    ankr_data: pd.DataFrame = pd.read_csv("data/ankr_data.csv").query(
        "level == 'info'"
    )[["time", "tx"]].reset_index(drop = True)

    ankr_data_exclusive_receipts: pd.DataFrame = ankr_data["tx"].apply(
        lambda hash: pd.Series(asyncio.get_event_loop().run_until_complete(get_transaction_receipt_for_hash(hash)))
    ).dropna(subset = "transactionHash")


    ankr_data_exclusive_receipts.to_csv("data/ankr_transaction_receipts.csv", index = False)


def get_block_data(block_number: BlockNumber):
    pass


if __name__ == "__main__":
    # fetch_transaction_data_from_raw()
    fetch_transaction_receipt_from_raw()

    # uniswap_contract: Address = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
    # ankr_data_exclusive: pd.DataFrame = pd.read_csv("data/ankr_transaction_data.csv")
    # print(ankr_data_exclusive.query(f"to == '{uniswap_contract}'"))