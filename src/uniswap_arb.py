from .services.uniswap_arbitrage_service import UniswapArbitrageService

from web3 import Web3, HTTPProvider
from dotenv import dotenv_values

from typing import Dict, Any
from pprint import pprint
from time import perf_counter

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

    for i in range(18100000, 20100001, 1000):
        print(i, end=" ")
        b = perf_counter()
        tokens = uniswap_arbitrage_service.uniswapv3_service.fetch_top_tokens(
            first = 12
        )
        # tokens = ["0x0590cc9232eBF68D81F6707A119898219342ecB9", "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"]
        pprint(
            uniswap_arbitrage_service.find_arbitrages(
                tokens = tokens,
                max_hops = 3,
                block_identifier = i
            )
        )
        print(perf_counter() - b)

if __name__ == "__main__":
    main()