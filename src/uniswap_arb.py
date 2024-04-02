from .services.uniswap_arbitrage_service import UniswapArbitrageService

from web3 import Web3, HTTPProvider
from dotenv import dotenv_values

from typing import Dict, Any
from pprint import pprint
from time import perf_counter, sleep
import json

# Load environment variables from .env
env: Dict[str, Any] = dotenv_values(".env")

def main() -> None:
    # Create a web3 object with a standard json rpc provider, such as Infura, Alchemy, or your own node.
    w3 = Web3(HTTPProvider(env.get("HTTP_PROVIDER_URL")))

    b = perf_counter()

    uniswap_arbitrage_service: UniswapArbitrageService = UniswapArbitrageService(
        w3 = w3,
        executor_private_key = env.get("WALLET_PRIVATE_KEY")
    )

    print(perf_counter() - b)

    b = perf_counter()
    # tokens = uniswap_arbitrage_service.uniswapv3_service.fetch_top_tokens(
    #     first = 20
    # )
    # pprint(tokens)
    tokens = ['0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
 '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
 '0xdAC17F958D2ee523a2206206994597C13D831ec7',
 '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599',
 '0x6B175474E89094C44Da98b954EedeAC495271d0F',
 '0x7f39C581F595B53c5cb19bD0b3f8dA6c935E2Ca0',
 '0x956F47F50A910163D8BF957Cf5846D573E7f87CA',
 '0x514910771AF9Ca656af840dff83E8264EcF986CA',
 '0x4d224452801ACEd8B2F0aebE155379bb5D594381',
 '0x2b591e99afE9f32eAA6214f7B7629768c40Eeb39',
 '0xa47c8bf37f92aBed4A126BDA807A7b7498661acD',
 '0x853d955aCEf822Db058eb8505911ED77F175b99e',
 '0xf4d2888d29D722226FafA5d9B24F9164c092421E',
 '0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984',
 '0x7D1AfA7B718fb893dB30A3aBc0Cfc608AaCfeBB0',
 '0x6982508145454Ce325dDbE47a25d4ec3d2311933',
 '0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE',
 '0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32',
 '0xC18360217D8F7Ab5e7c516566761Ea12Ce7F9D72',
 '0x92D6C1e31e14520e676a687F0a93788B716BEff5']
    print(perf_counter() - b)
    print(tokens)
    # tokens = ["0x0590cc9232eBF68D81F6707A119898219342ecB9", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"]
    
    for n in range(6, 7):
        data = []
        for i in range(19000000, 19410000, 10000):
            print(i, end=" ", flush = True)
            sample_tokens = tokens[:n]
            b = perf_counter()
            u_eth = uniswap_arbitrage_service.arbitrage_service.get_recommended_u_eth(block_number = i)
            s = list(
                uniswap_arbitrage_service.find_arbitrages(
                    tokens = sample_tokens,
                    u_eth = u_eth,
                    max_hops = 2,
                    block_identifier = i
                )
            )
            t = perf_counter() - b
            l = [
                i.asdict()
                for i in s
            ]
            print(t, len(l), flush = True)
            data.append(
                {
                    "block_number": i,
                    "num_of_tokens": len(sample_tokens),
                    "tokens": sample_tokens,
                    "u_eth": u_eth,
                    "time": t,
                    "arbitrages": l
                }
            )

            with open(f"data/naive_test_{n}_64.json", "w+t") as f:
                json.dump(data, f, default = lambda foo: str(foo))

            sleep(10)

if __name__ == "__main__":
    main()