from .contract_service import ContractService, Call, MulticallReturnData
from .price_feed_service import PriceFeedService
from .token_service import TokenService
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from web3.types import TxParams
from eth_typing.evm import ChecksumAddress, BlockNumber, BlockIdentifier

from dataclasses import dataclass, field
from typing_extensions import Self
from math import log2
from copy import deepcopy
from functools import cache
from typing import (
    Dict,
    List,
    Set,
    Callable,
    Iterable,
    Optional,
    Protocol,
    SupportsIndex,
    NewType
)

@dataclass(frozen = True)
class QuoteFunctionMeta():
    call: Call
    callback: Callable[[MulticallReturnData], int]

class QuoteFunctionType(Protocol):
    def __call__(
        self, token_in: ChecksumAddress, token_out: ChecksumAddress,
        amount_in: int, block_identifier: BlockIdentifier = "latest"
    ) -> QuoteFunctionMeta:
        ...

class SwapFuncionType(Protocol):
    def __call__(
        self, token_in: ChecksumAddress, token_out, ChecksumAddress,
        amount_in: int, wallet_address: ChecksumAddress,
        block_identifier: BlockIdentifier = "latest"
    ) -> TxParams:
        ...

@dataclass(frozen = True)
class ExchangeFunction():
    quote_function: QuoteFunctionType
    swap_function: SwapFuncionType

@dataclass(frozen = True)
class ExchangeEdge():
    # TODO add an id attribute
    token_in: ChecksumAddress
    token_out: ChecksumAddress
    exchange_function: ExchangeFunction

    def get_quote_function_meta(
        self, amount_in: int, block_identifier: BlockIdentifier = "latest"
    ) -> QuoteFunctionMeta:
        return self.exchange_function.quote_function(
            token_in = self.token_in,
            token_out = self.token_out,
            amount_in = amount_in,
            block_identifier = block_identifier
        )
    
    def create_transaction(
        self, amount_in: int, wallet_address: ChecksumAddress,
        block_identifier: BlockIdentifier = "latest"
    ) -> TxParams:
        return self.exchange_function.swap_function(
            token_in = self.token_in,
            token_out = self.token_out,
            amount_in = amount_in,
            wallet_address = wallet_address,
            block_identifier = block_identifier
        )
    

ExchangeEdgeDict = NewType(
    name = "ExchangeEdgeDict",
    tp = Dict[
        ChecksumAddress, Dict[
            ChecksumAddress, List[ExchangeEdge]
        ]
    ]
)

class ExchangeGraph():
    def __init__(
        self, tokens: List[ChecksumAddress], exchange_functions: List[ExchangeFunction]
    ) -> None:
        self.tokens: List[ChecksumAddress] = tokens
        self.num_of_tokens: int = len(self.tokens)

        self.exchange_functions: List[ExchangeFunction] = exchange_functions

        self.exchange_edge_dict: ExchangeEdgeDict = {
            token_in: {
                token_out: [
                    ExchangeEdge(
                        token_in = token_in,
                        token_out = token_out,
                        exchange_function = exchange_function
                    )
                    for exchange_function in self.exchange_functions
                ]
                for token_out in self.tokens
                if token_in != token_out
            }
            for token_in in self.tokens
        }

    
    def get_edges(
        self, token_in: ChecksumAddress, token_out: ChecksumAddress
    ) -> List[ExchangeEdge]:
        return self.exchange_edge_dict.get(token_in).get(token_out)
        

@dataclass
class Hop():
    exchange_edge: ExchangeEdge
    amount_in: int
    amount_out: int
    block_number: BlockNumber


class Path(List[Hop]):
    def __init__(self, __iterable: Iterable[Hop] = []) -> None:
        super().__init__(__iterable)
        self.tokens_involved: List[ChecksumAddress] = []
        for hop in __iterable:
            self.tokens_involved.append(
                hop.exchange_edge.token_in
            )
            self.tokens_involved.append(
                hop.exchange_edge.token_out
            )
    
    def append(self, __object: Hop):
        super().append(__object)
        self.tokens_involved.append(
            __object.exchange_edge.token_in
        )
        self.tokens_involved.append(
            __object.exchange_edge.token_out
        )

    def extend(self, __iterable: Iterable[Hop]) -> None:
        for hop in __iterable:
            self.append(hop)

    def __contains__(self, __key: object) -> bool:
        if isinstance(__key, str):
            return __key in self.tokens_involved
        return super().__contains__(__key)
    
    def pop(self, __index: SupportsIndex = -1) -> Hop:
        assert __index == -1, "Can only pop from the back."
        hop: Hop = super().pop()
        self.tokens_involved.pop()
        self.tokens_involved.pop()
        return hop
    
    def copy(self) -> Self:
        return self.__class__(
            super().copy()
        )


@dataclass
class Arbitrage():
    path: Path
    block_number: BlockNumber
    expected_gas: int

    token_in: int = field(init = False)
    amount_in: int = field(init = False)
    amount_out: int = field(init = False)
    return_precost: float = field(init = False)

    def __post_init__(self) -> None:
        self.token_in = self.path[0].exchange_edge.token_in

        self.amount_in = self.path[0].amount_in

        self.amount_out = self.path[-1].amount_out

        self.return_precost = self.amount_out / self.amount_in - 1


@dataclass
class Quote():
    token_in: ChecksumAddress
    token_out: ChecksumAddress
    amount_in: int
    amount_out: int

    exchange_rate: float = field(init = False)
    negative_log_exchange_rate: float = field(init = False)

    def __post_init__(self) -> None:
        self.exchange_rate = self.amount_out / self.amount_in
        self.negative_log_exchange_rate = (
            - log2(self.exchange_rate) if self.exchange_rate > 0 else float("inf")
        )


QuoteGraph = NewType(
    name = "QuoteGraph",
    tp = Dict[
        ChecksumAddress, Dict[
            ChecksumAddress, Dict[
                ExchangeEdge, Quote
            ]
        ]
    ]
)


class ArbitrageService():
    def __init__(self, w3: Web3, api_keys: Dict[str, str] = dict()) -> None:
        self.w3: Web3 = w3
        self.api_keys: Dict[str, str] = api_keys

        self.contract_service: ContractService = ContractService(w3 = self.w3)
        self.price_feed_service: PriceFeedService = PriceFeedService(w3 = self.w3)
        self.token_service: TokenService = TokenService(
            w3 = self.w3,
            bitquery_api_key = api_keys.get("bitquery")
        )


    def find_arbitrages_naive(
        self, exchange_graph: ExchangeGraph, max_hops: int,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        assert max_hops > 1, f"At least 2 hops are needed for an arbitrage. Given max_hops = {max_hops}."
        arbitrages: List[Arbitrage] = []
        
        base_fee_per_gas: int = self.contract_service.get_base_fee_per_gas(
            block_identifier = block_identifier
        )
        test_exposure_eth: float = base_fee_per_gas * 1e6
        token_prices_eth: Dict[ChecksumAddress, int] = self.price_feed_service.fetch_price_eth(
            tokens = exchange_graph.tokens,
            block_identifier = block_identifier
        )

        for token_in in exchange_graph.tokens:
            amount_in: int = round(
                test_exposure_eth * token_prices_eth.get(token_in) * 1e18
            )
            for hops in range(2, max_hops + 1):
                arbitrages.extend(
                    self.__find_arbitrages(
                        exchange_graph = exchange_graph,
                        hops = hops,
                        token_in = token_in,
                        amount_in = amount_in,
                        curr_path = Path(),
                        block_number = block_identifier_to_number(
                            w3 = self.w3,
                            block_identifier = block_identifier
                        )
                    )
                )
        
        return arbitrages


    def find_arbitrages_bellman_ford(
        self, exchange_graph: ExchangeGraph,
        max_hops: int = 4, block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        return self.__find_arbitrages_bellman_ford(
            exchange_graph = exchange_graph,
            max_hops = max_hops,
            block_number = block_identifier_to_number(
                w3 = self.w3,
                block_identifier = block_identifier
            )
        )
    

    def __find_arbitrages(
        self, exchange_graph: ExchangeGraph, hops: int,
        token_in: ChecksumAddress, amount_in: int,
        curr_path: Path, block_number: BlockNumber
    ) -> List[Arbitrage]:  
        curr_token_in: ChecksumAddress = curr_path[-1].exchange_edge.token_out if curr_path else token_in
        curr_amount_in: int = curr_path[-1].amount_out if curr_path else amount_in

        arbitrages: List[Arbitrage] = []

        if hops == 1:
            edges: List[ExchangeEdge] = exchange_graph.get_edges(
                token_in = curr_token_in,
                token_out = token_in
            )
            amount_out_list: List[int] = self.contract_service.multicall(
                calls = [
                    edge.get_quote_function_meta(
                        amount_in = curr_amount_in,
                        block_identifier = block_number
                    ).call
                    for edge in edges
                ],
                require_success = False,
                block_identifier = block_number,
                callback = lambda res: res.return_data[0] if res.success else 0
            )
            for edge, amount_out in zip(edges, amount_out_list):
                curr_path.append(
                    Hop(
                        exchange_edge = edge,
                        amount_in = curr_amount_in,
                        amount_out = amount_out,
                        block_number = block_number
                    )
                )
                if curr_path[-1].amount_out > amount_in:
                    arbitrages.append(
                        Arbitrage(
                            path = deepcopy(curr_path),
                            block_number = block_number
                        )
                    )
                curr_path.pop()
            return arbitrages

        for next_token in exchange_graph.tokens:
            if next_token in curr_path or curr_token_in == next_token:
                continue
            
            edges: List[ExchangeEdge] = exchange_graph.get_edges(
                token_in = curr_token_in,
                token_out = next_token
            )

            amount_out_list: List[int] = self.contract_service.multicall(
                calls = [
                    edge.get_quote_function_meta(
                        amount_in = curr_amount_in,
                        block_identifier = block_number
                    ).call
                    for edge in edges
                ],
                require_success = False,
                block_identifier = block_number,
                callback = lambda res: res.return_data[0] if res.success else 0
            )

            for edge, amount_out in zip(edges, amount_out_list):
                curr_path.append(
                    Hop(
                        exchange_edge = edge,
                        amount_in = curr_amount_in,
                        amount_out = amount_out,
                        block_number = block_number
                    )
                )
                arbitrages.extend(
                    self.__find_arbitrages(
                        exchange_graph = exchange_graph,
                        hops = hops - 1,
                        token_in = token_in,
                        amount_in = amount_in,
                        curr_path = deepcopy(curr_path),
                        block_number = block_number
                    )
                )
                curr_path.pop()
        
        return arbitrages
    

    def __find_arbitrages_bellman_ford(
        self, exchange_graph: ExchangeGraph,
        max_hops: int, block_number: BlockNumber
    ) -> List[Arbitrage]:
        base_fee_per_gas: int = self.contract_service.get_base_fee_per_gas(
            block_identifier = block_number
        )
        test_exposure_eth: float = base_fee_per_gas * 1e6

        tokens: List[ChecksumAddress] = exchange_graph.tokens

        token_prices_eth: Dict[ChecksumAddress, int] = self.price_feed_service.fetch_price_eth(
            tokens = tokens,
            block_identifier = block_number
        )

        amount_in_dict: Dict[ChecksumAddress, int] = {
            token_in: round(
                test_exposure_eth * token_prices_eth.get(token_in) * 1e18
            )
            for token_in in tokens
        }

        quote_graph: QuoteGraph = self.__construct_quote_graph(
            exchange_graph = exchange_graph,
            amount_in_dict = amount_in_dict,
            block_identifier = block_number
        )

        tokens: List[ChecksumAddress] = exchange_graph.tokens

        source: int = tokens[0]
        min_dist: Dict[ChecksumAddress, float] = {
            token_address: float("inf")
            for token_address in tokens
        }
        min_dist[source] = 0

        pre: Dict[ChecksumAddress, Optional[ExchangeEdge]] = {
            token_address: None
            for token_address in tokens
        }

        for _ in range(max_hops):
            for source_curr in tokens:
                for dest_curr in tokens:
                    if source_curr == dest_curr:
                        continue

                    quotes: Dict[ExchangeEdge, Quote] = quote_graph.get(
                        source_curr
                    ).get(
                        dest_curr
                    )
                    for edge in quotes:
                        dist: float = quotes.get(edge).negative_log_exchange_rate
                        if min_dist[dest_curr] > min_dist[source_curr] + dist:
                            min_dist[dest_curr] = min_dist[source_curr] + dist
                            pre[dest_curr] = edge

        arbitrages: List[Arbitrage] = []
        for source_curr in tokens:
            for dest_curr in tokens:
                if source_curr == dest_curr:
                    continue
                quotes: Dict[ExchangeEdge, Quote] = quote_graph.get(
                    source_curr
                ).get(
                    dest_curr
                )
                for edge in quotes:
                    dist: float = quotes.get(edge).negative_log_exchange_rate
                    if min_dist[dest_curr] <= min_dist[source_curr] + dist:
                        continue

                    path_meta: List[ExchangeEdge] = [edge]
                    involved_tokens: Set[ChecksumAddress] = {source_curr, dest_curr}
                    curr: ChecksumAddress = source_curr
                    while pre[curr].token_in not in involved_tokens:
                        path_meta.append(pre[curr])
                        involved_tokens.add(pre[curr].token_in)
                        curr = pre[curr].token_in
                    path_meta.append(pre[curr])

                    if path_meta[0].token_out != path_meta[-1].token_in:
                        continue

                    path_meta.reverse()
                
                    path: Path = Path()
                    amount_in: int = amount_in_dict.get(path_meta[0].token_in)
                    curr_amount: int = amount_in
                    for edge in path_meta:
                        # next_amount: int = round(
                        #     curr_amount
                        #     * quote_graph.get(
                        #         edge.token_in
                        #     ).get(
                        #         edge.token_out
                        #     ).get(
                        #         edge
                        #     ).exchange_rate
                        # )
                        quote_function_meta: QuoteFunctionMeta = edge.get_quote_function_meta(
                            amount_in = curr_amount,
                            block_identifier = block_number
                        )

                        next_amount: int = self.contract_service.multicall(
                            calls = [
                                quote_function_meta.call
                            ],
                            require_success = False,
                            block_identifier = block_number,
                            callbacks = [
                                quote_function_meta.callback
                            ]
                        )[0]

                        path.append(
                            Hop(
                                exchange_edge = edge,
                                amount_in = curr_amount,
                                amount_out = next_amount,
                                block_number = block_number
                            )
                        )
                        curr_amount = next_amount

                    if curr_amount > amount_in:
                        arbitrages.append(
                            Arbitrage(
                                path = path,
                                block_number = block_number,
                                expected_gas = 0
                                # expected_gas = self.estimate_gas(
                                #     path = path,
                                #     block_identifier = block_number
                                # )
                            )
                        )
        return arbitrages
                

    def __construct_quote_graph(
        self, exchange_graph: ExchangeGraph,
        amount_in_dict: Dict[ChecksumAddress, int],
        block_identifier: BlockIdentifier = "latest"
    ) -> QuoteGraph:
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        quote_graph: QuoteGraph = {
            token_in: {
                token_out: dict()
                for token_out in exchange_graph.tokens
                if token_out != token_in
            }
            for token_in in exchange_graph.tokens
        }

        for token_in in exchange_graph.tokens:
            for token_out in exchange_graph.tokens:
                if token_in == token_out:
                    continue

                amount_in: int = amount_in_dict.get(token_in)

                quote_function_meta_list: List[QuoteFunctionMeta] = [
                    edge.get_quote_function_meta(
                        amount_in = amount_in,
                        block_identifier = block_number
                    )
                    for edge in exchange_graph.get_edges(
                        token_in = token_in,
                        token_out = token_out
                    )
                ]
            
                amount_out_list: List[int] = self.contract_service.multicall(
                    calls = [
                        meta.call for meta in quote_function_meta_list
                    ],
                    require_success = False,
                    block_identifier = block_number,
                    callbacks = [
                        meta.callback for meta in quote_function_meta_list
                    ]
                )

                edges: List[ExchangeEdge] = exchange_graph.get_edges(
                    token_in = token_in,
                    token_out = token_out
                )
                for edge, amount_out in zip(edges, amount_out_list):
                    quote_graph[token_in][token_out][edge] = Quote(
                        token_in = token_in,
                        token_out = token_out,
                        amount_in = amount_in,
                        amount_out = amount_out
                    )
        return quote_graph
        
    #TODO estimate gas
    def estimate_gas(self, path: Path, block_identifier: BlockIdentifier = "latest") -> int:
        return sum(
            self.contract_service.estimate_gas(
                transaction = hop.exchange_edge.create_transaction(
                    amount_in = hop.amount_in,
                    wallet_address = self.get_wallet_proxy_for_token(
                        token_address = hop.exchange_edge.token_in,
                        block_identifier = block_identifier
                    ),
                    block_identifier = block_identifier
                ),
                block_identifier = block_identifier
            )
            for hop in path
        )
    
    @cache
    def get_wallet_proxy_for_token(
        self, token_address: ChecksumAddress, block_identifier: BlockIdentifier = "latest"
    ) -> ChecksumAddress:
        return self.token_service.fetch_top_token_holders(
            token_address = token_address,
            top = 1,
            block_identifier = block_identifier
        )[0]


    def optimize_arbitrage(self, arbitrage: Arbitrage) -> Arbitrage:
        # Find optimal input amount
        pass