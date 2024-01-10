from .exchange_service import ExchangeService
from .contract_service import ContractService
from .price_feed_service import PriceFeedService
from .thegraph_service import TheGraphService

from ..data_structures.call import Call, CallReturn
from ..data_structures.exchange_graph import QuoteFunctionMeta, ExchangeFunction
from ..utils.abi import get_abi

from web3 import Web3
from web3.contract.contract import Contract, ContractFunction
from web3.types import TxParams
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_typing.evm import ChecksumAddress, BlockIdentifier

from hexbytes import HexBytes
from typing import Any, List, Callable
from typing_extensions import Self


class UniswapV3Service(ExchangeService):
    # Quoter
    QUOTER_ADDRESS: ChecksumAddress = "0x61fFE014bA17989E743c5F6cB21bF9697530B21e"
    QUOTER_ABI: Any = get_abi("uniswapv3_quoter")

    # Router
    ROUTER_ADDRESS: ChecksumAddress = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"
    ROUTER_ABI: Any = get_abi("uniswapv3_router02")

    # Factory
    FACTORY_ADDRESS: ChecksumAddress = "0x1F98431c8aD98523631AE4a59f267346ea31F984"
    FACTORY_ABI: Any = get_abi("uniswapv3_factory")

    # ERC20
    ERC20_ABI: Any = get_abi("erc20")

    # TheGraph
    GRAPHQL_ENDPOINT: str = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"


    def __init__(self: Self, w3: Web3, executor_private_key: HexBytes) -> None:
        print("Initializing UniswapV3 Service")

        self.w3: Web3 = w3
        self.executor: LocalAccount = Account.from_key(executor_private_key)

        self.contract_service: ContractService = ContractService(w3 = self.w3)
        self.price_feed_service: PriceFeedService = PriceFeedService(w3 = self.w3)
        self.thegraph_service: TheGraphService = TheGraphService()

        self.quoter: Contract = self.contract_service.get_contract(
            address = self.QUOTER_ADDRESS,
            abi = self.QUOTER_ABI
        )

        self.router: Contract = self.contract_service.get_contract(
            address = self.ROUTER_ADDRESS,
            abi = self.ROUTER_ABI
        )

        self.factory: Contract = self.contract_service.get_contract(
            address = self.FACTORY_ADDRESS,
            abi = self.FACTORY_ABI
        )

    
    def get_exchange_functions(self, block_identifier: BlockIdentifier = "latest") -> List[ExchangeFunction]:
        quote_callback: Callable[[CallReturn], int] = lambda result: (
            result.return_data[0] if result.success else 0
        )

        return [
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.QUOTER_ADDRESS,
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
                        contract_abi = self.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.swap_exact_input_single(
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
                        contract_address = self.QUOTER_ADDRESS,
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
                        contract_abi = self.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.swap_exact_input_single(
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
                        contract_address = self.QUOTER_ADDRESS,
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
                        contract_abi = self.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.swap_exact_input_single(
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
                        contract_address = self.QUOTER_ADDRESS,
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
                        contract_abi = self.QUOTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.swap_exact_input_single(
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

    
    def swap_exact_input_single(
        self, token_in: ChecksumAddress, token_out: ChecksumAddress, fee: int,
        recipient: ChecksumAddress, amount_in: int, amount_out_minimum: int,
        sqrt_price_limit_x96: int, block_identifier: BlockIdentifier = "latest"
    ) -> TxParams:
        swap_func: ContractFunction = self.router.get_function_by_name("exactInputSingle")(
            (
                token_in,
                token_out,
                fee,
                recipient,
                0,
                amount_out_minimum,
                sqrt_price_limit_x96
            )
        )

        # print(swap_func.estimate_gas(
        #     transaction = {
        #         "from": recipient,
        #         "nonce": self.w3.eth.get_transaction_count(recipient)
        #     },
        #     block_identifier = block_identifier
        # ))

        return swap_func.build_transaction()


    def fetch_top_tokens(self, first: int = 10) -> Any:
        return list(map(
            lambda item: self.w3.to_checksum_address(item.get("id")),
            self.thegraph_service.query(
                url = self.GRAPHQL_ENDPOINT,
                query = '''
                    query FetchTopTokens {{
                        tokens(orderDirection: desc, orderBy: volumeUSD, first: {}) {{
                            id
                        }}
                    }}
                '''.format(first)
            ).get("data").get("tokens")
        ))