from ...services.price_feed_service import PriceFeedService

from web3 import Web3, HTTPProvider
from eth_typing.evm import ChecksumAddress
from dotenv import dotenv_values
import pandas as pd

from time import perf_counter
from random import sample
from typing import Dict, Any, List

env: Dict[str, Any] = dotenv_values(".env")
w3: Web3 = Web3(HTTPProvider(env.get("HTTP_PROVIDER_URL")))
test_tokens: List[ChecksumAddress] = ['0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', '0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x956F47F50A910163D8BF957Cf5846D573E7f87CA', '0x4d224452801ACEd8B2F0aebE155379bb5D594381', '0x514910771AF9Ca656af840dff83E8264EcF986CA', '0x2b591e99afE9f32eAA6214f7B7629768c40Eeb39', '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD', '0xf4d2888d29D722226FafA5d9B24F9164c092421E', '0x853d955aCEf822Db058eb8505911ED77F175b99e', '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0', '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0', '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', '0x6982508145454Ce325dDbE47a25d4ec3d2311933', '0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32', '0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72', '0x92D6C1e31e14520e676a687F0a93788B716BEff5', '0xAa6E8127831c9DE45ae56bB1b0d4D4Da6e5665BD', '0x8E870D67F660D95d5be530380D0eC0bd388289E1', '0x5f98805A4E8be255a32880FDeC7F6728C6568bA0', '0x1a7e4e63778B4f12a199C062f3eFdD288afCBce8', '0xBB0E17EF65F82Ab018d8EDd776e8DD940327B28b', '0x4Fabb145d64652a948d72533023f6E7A623C7C53', '0xBe9895146f7AF43049ca1c1AE358B0541Ea49704', '0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2', '0x5283D291DBCF85356A21bA090E6db59121208b44', '0xC581b735A1688071A1746c968e0798D642EDE491']

def perf_test_simple(calls: List[Dict[str, Any]], block_number: int) -> List[float]:
    price_feed_service: PriceFeedService = PriceFeedService(
        w3 = w3
    )

    begin = perf_counter()
    price_feed_service.contract_service.batch_call_simple(
        calls = calls,
        require_success = True,
        block_identifier = block_number,
        callbacks = None
    )

    return perf_counter() - begin


def perf_test_multithreading(calls: List[Dict[str, Any]], block_number: int) -> List[float]:
    price_feed_service: PriceFeedService = PriceFeedService(
        w3 = w3
    )

    begin = perf_counter()
    price_feed_service.contract_service.batch_call_multithreading(
        calls = calls,
        require_success = True,
        block_identifier = block_number,
        callbacks = None
    )

    return perf_counter() - begin


def perf_test_multicall(calls: List[Dict[str, Any]], block_number: int) -> List[float]:
    price_feed_service: PriceFeedService = PriceFeedService(
        w3 = w3
    )
    
    begin = perf_counter()
    try:
        price_feed_service.contract_service.multicall(
            calls = calls,
            require_success = True,
            block_identifier = block_number,
            callbacks = None
        )

        return perf_counter() - begin
    except ValueError:
        print("multicall error")
        return -1


def perf_test_fetch_price(block_number: int, n: int = 8):
    perf_test_result: List[Dict[str, Any]] = []
    for nums_of_tokens in range(1, len(test_tokens) + 1):
        for iter in range(1, n + 1):
            print(nums_of_tokens, iter)
            calls:  List[Dict[str, Any]] = [
                {
                    "contract_address": PriceFeedService.SPOT_AGGREGATOR_1INCH_ADDRESS,
                    "function_name": "getRateToEth",
                    "args": [
                        token_address,
                        True
                    ],
                    "output_types": [
                        "uint256"
                    ]
                }
                for token_address in sample(population = test_tokens, k = nums_of_tokens)
            ]

            perf_test_result.extend([
                {
                    "nums_of_tokens": nums_of_tokens,
                    "iter": iter,
                    "method": "synchronous",
                    "runtime": perf_test_simple(
                        calls = calls,
                        block_number = block_number
                    )
                },
                {
                    "nums_of_tokens": nums_of_tokens,
                    "iter": iter,
                    "method": "asynchronous",
                    "runtime": perf_test_multithreading(
                        calls = calls,
                        block_number = block_number
                    )
                },
                {
                    "nums_of_tokens": nums_of_tokens,
                    "iter": iter,
                    "method": "multicall",
                    "runtime": perf_test_multicall(
                        calls = calls,
                        block_number = block_number
                    )
                }
            ])
    return pd.DataFrame(perf_test_result)


def main():
    df = perf_test_fetch_price(block_number = 18100000)
    df.to_csv("data/perf_test_price_feed.csv", index = False)


if __name__ == "__main__":
    main()