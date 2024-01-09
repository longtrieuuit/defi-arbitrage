from ...services.uniswapv3_service import UniswapV3Service, FeeAmount

from web3 import Web3, HTTPProvider
from eth_typing.evm import ChecksumAddress
from dotenv import dotenv_values
import pandas as pd

from time import perf_counter
from random import sample
from typing import Dict, Any, List

env: Dict[str, Any] = dotenv_values(".env")
w3: Web3 = Web3(HTTPProvider(env.get("HTTP_PROVIDER_URL")))
test_tokens: List[ChecksumAddress] = ['0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', '0xdAC17F958D2ee523a2206206994597C13D831ec7', '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', '0x6B175474E89094C44Da98b954EedeAC495271d0F', '0x956F47F50A910163D8BF957Cf5846D573E7f87CA', '0x4d224452801ACEd8B2F0aebE155379bb5D594381', '0x514910771AF9Ca656af840dff83E8264EcF986CA', '0x2b591e99afE9f32eAA6214f7B7629768c40Eeb39', '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD', '0xf4d2888d29D722226FafA5d9B24F9164c092421E', '0x853d955aCEf822Db058eb8505911ED77F175b99e', '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0', '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984', '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0', '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE', '0x6982508145454Ce325dDbE47a25d4ec3d2311933', '0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32', '0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72', '0x92D6C1e31e14520e676a687F0a93788B716BEff5']
test_token_in: ChecksumAddress = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
test_amount_in: int = int(1e18)

def perf_test_simple(calls: List[Dict[str, Any]], block_number: int) -> List[float]:
    uniswapv3_service: UniswapV3Service = UniswapV3Service(
        w3 = w3,
        executor_private_key = env.get("WALLET_PRIVATE_KEY")
    )

    begin = perf_counter()
    uniswapv3_service.contract_service.batch_call_simple(
        calls = calls,
        require_success = False,
        block_identifier = block_number,
        callbacks = None
    )

    return perf_counter() - begin


def perf_test_multithreading(calls: List[Dict[str, Any]], block_number: int) -> List[float]:
    uniswapv3_service: UniswapV3Service = UniswapV3Service(
        w3 = w3,
        executor_private_key = env.get("WALLET_PRIVATE_KEY")
    )

    begin = perf_counter()
    uniswapv3_service.contract_service.batch_call_multithreading(
        calls = calls,
        require_success = False,
        block_identifier = block_number,
        callbacks = None
    )

    return perf_counter() - begin


def perf_test_multicall(calls: List[Dict[str, Any]], block_number: int) -> List[float]:
    uniswapv3_service: UniswapV3Service = UniswapV3Service(
        w3 = w3,
        executor_private_key = env.get("WALLET_PRIVATE_KEY")
    )
    
    begin = perf_counter()
    try:
        uniswapv3_service.contract_service.multicall(
            calls = calls,
            require_success = False,
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
                    "contract_address": UniswapV3Service.QUOTER_ADDRESS,
                    "function_name": "quoteExactInputSingle",
                    "args": [
                        (
                            test_token_in,
                            token_out, 
                            test_amount_in,
                            fee_amount.value,
                            0
                        )
                    ],
                    "output_types": [
                        "uint256", "uint160", "uint32", "uint256"
                    ] # (amountOut, sqrtPriceX96After, initializedTicksCrossed, gasEstimate)
                }
                for token_out in sample(population = test_tokens, k = nums_of_tokens)
                if test_token_in != token_out
                for fee_amount in FeeAmount
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
    df.to_csv("data/perf_test_quote.csv", index = False)


if __name__ == "__main__":
    main()