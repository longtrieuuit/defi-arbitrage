from .arbitrage_service import ArbitrageService, ExchangeGraph, Arbitrage
from .uniswapv2_arbitrage_service import UniswapV2ArbitrageService
from .uniswapv3_arbitrage_service import UniswapV3ArbitrageService

from ..data_structures.exchange_graph import ExchangeFunction
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_typing.evm import ChecksumAddress, BlockIdentifier, BlockNumber

from hexbytes import HexBytes
from typing import List, Dict

class UniswapArbitrageService():
    def __init__(self, w3: Web3, executor_private_key: HexBytes, api_keys: Dict[str, str]) -> None:
        print("Initializing Uniswap Arbitrage Service")

        self.w3: Web3 = w3
        self.executor: LocalAccount = Account.from_key(executor_private_key)
        self.api_keys: Dict[str, str] = api_keys
        
        self.arbitrage_service: ArbitrageService = ArbitrageService(
            w3 = self.w3,
            api_keys = self.api_keys
        )

        self.uniswapv2_arbitrage_service: UniswapV2ArbitrageService = UniswapV2ArbitrageService(
            w3 = self.w3,
            executor_private_key = executor_private_key
        )

        self.uniswapv3_arbitrage_service: UniswapV3ArbitrageService = UniswapV3ArbitrageService(
            w3 = self.w3,
            executor_private_key = executor_private_key
        )

    def find_arbitrages(
        self, tokens: List[ChecksumAddress], max_hops: int = 3,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        exchange_functions: List[ExchangeFunction] = (
            self.uniswapv2_arbitrage_service.get_exchange_functions(block_identifier = block_number)
            + self.uniswapv3_arbitrage_service.get_exchange_functions(block_identifier = block_number)
        )

        return self.arbitrage_service.find_arbitrages_bellman_ford(
            exchange_graph = ExchangeGraph(
                tokens = tokens,
                exchange_functions = exchange_functions
            ),
            max_hops = max_hops,
            block_identifier = block_identifier
        )