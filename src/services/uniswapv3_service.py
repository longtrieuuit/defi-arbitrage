from .contract_service import ContractService
from .price_feed_service import PriceFeedService
from .thegraph_service import TheGraphService

from ..utils.abi import get_abi

from web3 import Web3
from web3.constants import ADDRESS_ZERO
from web3.contract import Contract, ContractFunction
from web3.types import TxParams
from eth_typing.evm import ChecksumAddress, BlockIdentifier
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_abi.packed import encode_packed
import pandas as pd

from enum import Enum
from typing import List, Any, Dict, DefaultDict, Union, NewType
from hexbytes import HexBytes
from collections import defaultdict
from dataclasses import dataclass, field
from math import log2


class FeeAmount(Enum):
    LOWEST = 100
    LOW = 500
    MEDIUM = 3000
    HIGH = 10000

    @classmethod
    def decimals() -> int:
        return 6


@dataclass
class Quote():
    token_in: ChecksumAddress
    token_out: ChecksumAddress
    fee_amount: int
    token_in_decimals: int
    token_out_decimals: int
    amount_in: int
    amount_out: int
    gas_estimate: int
    initialized_ticks_crossed: int
    sqrt_price_x96_after: int
    exchange_rate: float = field(init = False)
    negative_log_exchange_rate: float = field(init = False)

    def __post_init__(self) -> None:
        self.exchange_rate = (
            self.amount_out
            / self.amount_in
            / 10 ** (
                self.token_out_decimals - self.token_in_decimals
            )
        )

        self.negative_log_exchange_rate = - log2(self.exchange_rate) if self.exchange_rate > 0 else float("inf")


PoolMap = NewType(
    "PoolMap",
    DefaultDict[
        ChecksumAddress,
        DefaultDict[
            ChecksumAddress,
            DefaultDict[
                int,
                ChecksumAddress
            ]
        ]
    ]
)

QuoteGraph = NewType(
    "QuoteGraph",
    DefaultDict[
        ChecksumAddress,
        DefaultDict[
            ChecksumAddress,
            DefaultDict[
                int, 
                Quote
            ]
        ]
    ]
) # (V, E) = (token, quote)


class UniswapV3Service:
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

    # USD Proxy
    USD_ADDRESS: ChecksumAddress = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # USDC
    USD_DECIMALS: int = 6

    # TheGraph
    GRAPHQL_ENDPOINT: str = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"

    def __init__(self, w3: Web3, executor_private_key: HexBytes) -> None:
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

    
    def get_fee_amounts(self) -> List[int]:
        return [fee_amount.value for fee_amount in FeeAmount]
    

    def fetch_top_tokens(self, first: int = 10) -> Any:
        return list(map(
            lambda item: self.w3.to_checksum_address(item.get("id")),
            self.__thegraph_query(
                query = '''
                    query FetchTopTokens {{
                        tokens(orderDirection: desc, orderBy: volumeUSD, first: {}) {{
                            id
                        }}
                    }}
                '''.format(first)
            ).get("data").get("tokens")
        ))
    
    def quote_exact_input_single(
        self, token_in: ChecksumAddress, token_out: ChecksumAddress,
        amount_in: int, fee: int, sqrt_price_limit_x96: int,
        block_identifier: BlockIdentifier = "latest"
    ) -> int:
        # print(fee)
        try:
            return self.quoter.get_function_by_name("quoteExactInputSingle")(
                (
                    token_in,
                    token_out,
                    amount_in,
                    fee,
                    sqrt_price_limit_x96
                )
            ).call(
                block_identifier = block_identifier
            )
        except Exception as e:
            raise e

    def quote_exact_input(
        self, amount_in: int, route: List[Union[ChecksumAddress, int]],
        block_identifier: BlockIdentifier = "latest"
    ) -> Dict[str, int]:
        return {
            key: val
            for key, val in zip(
                ("amount_out", "sqrt_price_x96_after", "initialized_ticks_crossed", "expected_gas"), 
                self.quoter.get_function_by_name("quoteExactInput")(
                    encode_packed(
                        types = ["address" if isinstance(item, str) else "uint24" for item in route],
                        args = route
                    ),
                    amount_in
                ).call(
                    block_identifier = block_identifier
                )
            )
        }


    def fetch_quotes(
        self, tokens: List[ChecksumAddress], exposure_usd: float = 1,
        block_identifier: BlockIdentifier = "latest",
        as_dataframe: bool = False
    ) -> Union[QuoteGraph, pd.DataFrame]:
        token_prices_usd: Dict[ChecksumAddress, float] = self.__get_token_prices_usd(
            tokens = tokens,
            block_identifier = block_identifier
        )

        token_decimals: Dict[ChecksumAddress, int] = self.price_feed_service.fetch_token_decimals(
            tokens = tokens,
            block_identifier = block_identifier
        )

        quotes: QuoteGraph = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: None
                )
            )
        )
        
        for token_in in tokens:
            if token_prices_usd.get(token_in) is None:
                continue

            amount_in: int = round(
                exposure_usd * 10 ** token_decimals.get(token_in) / token_prices_usd.get(token_in)
            )

            quotes_list: List[Dict[str, Any]] = list(map(
                lambda result: {
                    key: value
                    for key, value in zip(
                        ("amount_out", "sqrt_price_x96_after", "initialized_ticks_crossed", "gas_estimate"),
                        result.return_data
                    ) 
                } if result.success else None, 
                self.contract_service.multicall(
                    calls = [
                        {
                            "contract_address": self.QUOTER_ADDRESS,
                            "function_name": "quoteExactInputSingle",
                            "args": [
                                (
                                    token_in,
                                    token_out, 
                                    amount_in,
                                    fee_amount.value,
                                    0
                                )
                            ],
                            "output_types": [
                                "uint256", "uint160", "uint32", "uint256"
                            ] # (amountOut, sqrtPriceX96After, initializedTicksCrossed, gasEstimate)
                        }
                        for token_out in tokens
                        if token_in != token_out and token_prices_usd.get(token_out) is not None
                        for fee_amount in FeeAmount
                    ],
                    require_success = False,
                    block_identifier = block_identifier
                )
            ))

            index: int = 0
            for token_out in tokens:
                if token_in == token_out or token_prices_usd.get(token_out) is None:
                    continue
                for fee_amount in FeeAmount:
                    if quotes_list[index] is not None:
                        quotes[token_in][token_out][fee_amount.value] = Quote(
                            token_in = token_in,
                            token_out = token_out,
                            fee_amount = fee_amount.value,
                            token_in_decimals = token_decimals.get(token_in),
                            token_out_decimals = token_decimals.get(token_out),
                            amount_in = amount_in,
                            **quotes_list[index]
                        )
                    index += 1

        if as_dataframe:
            return pd.DataFrame(
                quote
                for i in quotes.values()
                for j in i.values()
                for quote in j.values()
            )
        
        return quotes
    

    def get_pools(self, tokens: List[ChecksumAddress], block_identifier: BlockIdentifier = "latest") -> PoolMap:
        pools_list: List[ChecksumAddress] = list(map(
            lambda result: self.w3.to_checksum_address(result.return_data[0]) if result.success else None, 
            self.contract_service.multicall(
                calls = [
                    {
                        "contract_address": self.FACTORY_ADDRESS,
                        "function_name": "getPool",
                        "args": [token_1, token_2, fee_amount.value],
                        "output_types": ["address"]
                    }
                    for token_1 in tokens
                    for token_2 in tokens
                    if token_1 != token_2
                    for fee_amount in FeeAmount
                ],
                require_success = True,
                block_identifier = block_identifier
            )
        ))

        pools: PoolMap = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: ADDRESS_ZERO
                )
            )
        )

        index: int = 0
        for token_1 in tokens:
            for token_2 in tokens:
                if token_1 == token_2:
                    continue
                for fee_amount in FeeAmount:
                    pools[token_1][token_2][fee_amount.value] = pools_list[index]
                    pools[token_2][token_1][fee_amount.value] = pools_list[index]
                    index += 1

        return pools
    

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

    def __get_token_prices_usd(
        self, tokens: List[ChecksumAddress],
        block_identifier: BlockIdentifier = "latest"
    ) -> Dict[ChecksumAddress, float]:
        return self.price_feed_service.fetch_price_usd(
            tokens = tokens,
            block_identifier = block_identifier
        )


    def __thegraph_query(self, query: str) -> Any:
        return self.thegraph_service.query(
            url = self.GRAPHQL_ENDPOINT,
            query = query
        )