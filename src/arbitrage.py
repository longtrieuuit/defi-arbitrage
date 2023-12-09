from .services.flashbots_service import FlashbotsService
from .services.contract_service import ContractService
from .services.uniswap_arbitrage_service import UniswapArbitrageService

from web3 import Web3, HTTPProvider
from dotenv import dotenv_values

from typing import Dict, Any
from pprint import pprint
from time import perf_counter, sleep

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

    # Initialize contract service
    contract_service: ContractService = ContractService(
        w3 = w3
    )

    uniswap_arbitrage_service: UniswapArbitrageService = UniswapArbitrageService(
        w3 = w3,
        executor_private_key = env.get("WALLET_PRIVATE_KEY")
    )
    
    # uniswap_arbitrage_service.fecth_quotes(
    #     10,
    #     as_dataframe = True
    # ).to_csv("data/sample_quotes.csv")

    # for capital in [1, 5, 10, 50, 100, 1000, 5000, 10000, 20000, 50000, 100000]:
    #     print(f"Capital exposure: ${capital}")
    #     b = perf_counter()
        
    #     a = uniswap_arbitrage_service.find_arbitrage(capital, 14520237, False)
    #     pprint(a)
    #     print(len(a))
    #     print(f"Finished in {perf_counter() - b}")

    for i in range(18100000, 20000001, 1000):
        print(i, end=" ")
        b = perf_counter()
        pprint(
            uniswap_arbitrage_service.find_optimal_arbitrages(
                block_identifier = i
            )
        )
        print(perf_counter() - b)

if __name__ == "__main__":
    main()