from .contract_service import Call, CallReturn
from .uniswapv2_service import UniswapV2Service
from .arbitrage_service import ArbitrageService, ExchangeGraph, Arbitrage, QuoteFunctionMeta

from ..data_structures.exchange_graph import ExchangeFunction
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_typing.evm import ChecksumAddress, BlockIdentifier, BlockNumber

from hexbytes import HexBytes
from typing import List, Callable

class UniswapV2ArbitrageService():
    def __init__(self, w3: Web3, executor_private_key: HexBytes) -> None:
        print("Initializing UniswapV2 Arbitrage Service")

        self.w3: Web3 = w3
        self.executor: LocalAccount = Account.from_key(executor_private_key)
        
        self.uniswapv2_service: UniswapV2Service = UniswapV2Service(
            w3 = self.w3,
            executor_private_key = executor_private_key
        )
        self.arbitrage_service: ArbitrageService = ArbitrageService(
            w3 = self.w3
        )

    
    def get_exchange_functions(self, block_identifier: BlockIdentifier = "latest") -> List[ExchangeFunction]:
        quote_callback: Callable[[CallReturn], int] = lambda result: (
            result.return_data[0][1] if result.success else 0
        )

        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        next_block_time: int = self.w3.eth.get_block(
            block_identifier = block_number + 1
        ).get("timestamp")

        return [
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.uniswapv2_service.ROUTER_ADDRESS,
                        function_name = "getAmountsOut",
                        args = [
                            amount_in,
                            [token_in, token_out]
                        ],
                        output_types = [
                            "uint256[]"
                        ],
                        contract_abi = self.uniswapv2_service.ROUTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.uniswapv2_service.swap_exact_input(
                        amount_in = amount_in,
                        amount_out_minimum = amount_in,
                        path = [token_in, token_out],
                        recipient = wallet_address,
                        deadline = next_block_time,
                        block_identifier = block_number
                    )
                )
            )
        ]

    
    def find_arbitrages(
        self, top_tokens: int = 4, max_hops: int = 3,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        tokens: List[ChecksumAddress] = self.uniswapv2_service.fetch_top_tokens(
            first = top_tokens
        )

        exchange_functions: List[ExchangeFunction] = self.get_exchange_functions()

        return self.arbitrage_service.find_arbitrages_bellman_ford(
            exchange_graph = ExchangeGraph(
                tokens = tokens,
                exchange_functions = exchange_functions
            ),
            max_hops = max_hops,
            block_identifier = block_identifier
        )