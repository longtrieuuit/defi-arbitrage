from .contract_service import Call, CallReturn
from .uniswapv3_service import UniswapV3Service
from .arbitrage_service import ArbitrageService, ExchangeGraph, Arbitrage, QuoteFunctionMeta

from ..data_structures.exchange_graph import ExchangeFunction

from web3 import Web3
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_typing.evm import ChecksumAddress, BlockIdentifier

from hexbytes import HexBytes
from typing import List, Callable

class UniswapV3ArbitrageService():
    def __init__(self, w3: Web3, executor_private_key: HexBytes) -> None:
        print("Initializing UniswapV3 Arbitrage Service")

        self.w3: Web3 = w3
        self.executor: LocalAccount = Account.from_key(executor_private_key)
        
        self.uniswapv3_service: UniswapV3Service = UniswapV3Service(
            w3 = self.w3,
            executor_private_key = executor_private_key
        )
        self.arbitrage_service: ArbitrageService = ArbitrageService(
            w3 = self.w3
        )

    
    def get_exchange_functions(self, block_identifier: BlockIdentifier = "latest") -> List[ExchangeFunction]:
        quote_callback: Callable[[CallReturn], int] = lambda result: (
            result.return_data[0] if result.success else 0
        )
        return [
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.uniswapv3_service.QUOTER_ADDRESS,
                        function_name = "quoteExactInputSingle",
                        args = [
                            (
                                token_in,
                                token_out,
                                amount_in,
                                100,
                                0
                            )
                        ],
                        output_types = [
                            "uint256", "uint160", "uint32", "uint256"
                        ],
                        contract_abi = self.uniswapv3_service.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.uniswapv3_service.swap_exact_input_single(
                        token_in = token_in,
                        token_out = token_out,
                        fee = 100,
                        recipient = wallet_address,
                        amount_in = amount_in,
                        amount_out_minimum = 0,
                        sqrt_price_limit_x96 = 0,
                        block_identifier = block_identifier
                    )
                )
            ),
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.uniswapv3_service.QUOTER_ADDRESS,
                        function_name = "quoteExactInputSingle",
                        args = [
                            (
                                token_in,
                                token_out,
                                amount_in,
                                500,
                                0
                            )
                        ],
                        output_types = [
                            "uint256", "uint160", "uint32", "uint256"
                        ],
                        contract_abi = self.uniswapv3_service.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.uniswapv3_service.swap_exact_input_single(
                        token_in = token_in,
                        token_out = token_out,
                        fee = 500,
                        recipient = wallet_address,
                        amount_in = amount_in,
                        amount_out_minimum = amount_in,
                        sqrt_price_limit_x96 = 0,
                        block_identifier = block_identifier
                    )
                )
            ),
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.uniswapv3_service.QUOTER_ADDRESS,
                        function_name = "quoteExactInputSingle",
                        args = [
                            (
                                token_in,
                                token_out,
                                amount_in,
                                3000,
                                0
                            )
                        ],
                        output_types = [
                            "uint256", "uint160", "uint32", "uint256"
                        ],
                        contract_abi = self.uniswapv3_service.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.uniswapv3_service.swap_exact_input_single(
                        token_in = token_in,
                        token_out = token_out,
                        fee = 3000,
                        recipient = wallet_address,
                        amount_in = amount_in,
                        amount_out_minimum = 0,
                        sqrt_price_limit_x96 = 0,
                        block_identifier = block_identifier
                    )
                )
            ),
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.uniswapv3_service.QUOTER_ADDRESS,
                        function_name = "quoteExactInputSingle",
                        args = [
                            (
                                token_in,
                                token_out,
                                amount_in,
                                10000,
                                0
                            )
                        ],
                        output_types = [
                            "uint256", "uint160", "uint32", "uint256"
                        ],
                        contract_abi = self.uniswapv3_service.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.uniswapv3_service.swap_exact_input_single(
                        token_in = token_in,
                        token_out = token_out,
                        fee = 10000,
                        recipient = wallet_address,
                        amount_in = amount_in,
                        amount_out_minimum = 0,
                        sqrt_price_limit_x96 = 0,
                        block_identifier = block_identifier
                    )
                )
            )
        ]

    
    def find_arbitrages(
        self, top_tokens: int = 4, max_hops: int = 3,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        tokens: List[ChecksumAddress] = self.uniswapv3_service.fetch_top_tokens(
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