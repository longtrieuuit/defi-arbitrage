from .arbitrage_service import ArbitrageService, ExchangeGraph, Arbitrage
from .uniswapv2_service import UniswapV2Service
from .uniswapv3_service import UniswapV3Service

from ..data_structures.exchange_graph import ExchangeFunction
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_typing.evm import ChecksumAddress, BlockIdentifier, BlockNumber

from hexbytes import HexBytes
from typing import List, Generator

class UniswapArbitrageService():
    def __init__(self, w3: Web3, executor_private_key: HexBytes) -> None:
        print("Initializing Uniswap Arbitrage Service")

        self.w3: Web3 = w3
        self.executor: LocalAccount = Account.from_key(executor_private_key)
        
        self.arbitrage_service: ArbitrageService = ArbitrageService(
            w3 = self.w3
        )

        self.uniswapv2_service: UniswapV2Service = UniswapV2Service(
            w3 = self.w3,
            executor_private_key = executor_private_key
        )

        self.uniswapv3_service: UniswapV3Service = UniswapV3Service(
            w3 = self.w3,
            executor_private_key = executor_private_key
        )

    def find_arbitrages(
        self, tokens: List[ChecksumAddress], u_eth: float,
        max_hops: int = 3, block_identifier: BlockIdentifier = "latest"
    ) -> Generator[Arbitrage, None, None]:
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        exchange_functions: List[ExchangeFunction] = (
            self.uniswapv2_service.get_exchange_functions(block_identifier = block_number)
            + self.uniswapv3_service.get_exchange_functions(block_identifier = block_number)
        )

        yield from self.arbitrage_service.find_arbitrages_bellman_ford(
            exchange_graph = ExchangeGraph(
                tokens = tokens,
                exchange_functions = exchange_functions
            ),
            u_eth = u_eth,
            max_hops = max_hops,
            block_identifier = block_identifier
        )