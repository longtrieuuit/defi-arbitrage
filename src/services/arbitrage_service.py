from .contract_service import ContractService
from .price_feed_service import PriceFeedService

from ..data_structures.exchange_graph import QuoteFunctionMeta, ExchangeEdge, ExchangeGraph
from ..data_structures.quote_graph import Quote, QuoteGraph
from ..data_structures.arbitrage import Hop, Path, Arbitrage
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from eth_typing.evm import ChecksumAddress, BlockNumber, BlockIdentifier
import numpy

from multiprocessing.pool import ThreadPool
from copy import deepcopy
from typing import (
    Dict,
    List,
    Generator,
    Optional
)
from typing_extensions import Self
from dataclasses import asdict
from itertools import chain


class ArbitrageService():
    def __init__(self: Self, w3: Web3) -> None:
        self.w3: Web3 = w3

        self.contract_service: ContractService = ContractService(
            w3 = self.w3
        )
        self.price_feed_service: PriceFeedService = PriceFeedService(
            w3 = self.w3
        )

    
    def get_recommended_u_eth(self: Self, block_number: BlockNumber) -> float:
        base_fee_per_gas: int = self.contract_service.get_base_fee_per_gas(
            block_identifier = block_number
        )
        return base_fee_per_gas * 1e7

    
    def find_arbitrages_naive(
        self: Self, exchange_graph: ExchangeGraph, u_eth: Optional[float] = None,
        max_hops: int = 3, block_identifier: BlockIdentifier = "latest"
    ) -> Generator[Arbitrage, None, None]:
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        if u_eth is None:
            u_eth: float = self.get_recommended_u_eth(block_number = block_number)

        token_prices_eth: Dict[ChecksumAddress, int] = self.price_feed_service.fetch_price_eth(
            tokens = exchange_graph.tokens,
            block_identifier = block_number
        )

        with ThreadPool() as pool:
            yield from chain.from_iterable(
                pool.map(
                    func = lambda tup: list(self.__find_arbitrages_naive(
                        exchange_graph = exchange_graph,
                        hops = tup[1],
                        token_in = tup[0],
                        amount_in = round(
                            u_eth * token_prices_eth.get(tup[0]) * 1e18
                        ),
                        curr_path = Path(),
                        block_number = block_number
                    )),
                    iterable = (
                        (token_in, hops)
                        for hops in range(2, max_hops + 1)
                        for token_in in exchange_graph.tokens
                    )
                )
            )


    def find_arbitrages_bellman_ford(
        self: Self, exchange_graph: ExchangeGraph, u_eth: Optional[float] = None,
        max_hops: int = 3, block_identifier: BlockIdentifier = "latest"
    ) -> Generator[Arbitrage, None, None]:
        assert max_hops > 1, f"At least 2 hops are needed for an arbitrage. Given max_hops = {max_hops}."
        
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        if u_eth is None:
            u_eth: float = self.get_recommended_u_eth(block_number = block_number)

        quote_graph: QuoteGraph = self.__construct_quote_graph(
            exchange_graph = exchange_graph,
            u_eth = u_eth,
            block_number = block_number
        )

        path_meta_list: Generator[List[ExchangeEdge], None, None] = quote_graph.find_potential_arbitrage_path_meta()

        with ThreadPool() as pool:
            yield from filter(
                lambda arbitrage: arbitrage is not None,
                pool.map(
                    func = lambda path_meta: self.evaluate_arbitrage(
                        path_meta = path_meta,
                        amount_in = quote_graph.get_quote(
                            path_meta[0]
                        ).amount_in,
                        block_number = block_number
                    ),
                    iterable = path_meta_list
                )
            )


    def __construct_quote_graph(
        self: Self, exchange_graph: ExchangeGraph,
        u_eth: float, block_number: BlockNumber
    ) -> QuoteGraph:
        token_prices_eth: Dict[ChecksumAddress, int] = self.price_feed_service.fetch_price_eth(
            tokens = exchange_graph.tokens,
            block_identifier = block_number
        )

        amount_in_dict: Dict[ChecksumAddress, int] = {
            token_in: round(
                u_eth * token_prices_eth.get(token_in) * 1e18
            )
            for token_in in exchange_graph.tokens
        }

        quote_graph: QuoteGraph = QuoteGraph(block_number = block_number)

        edges: List[ExchangeEdge] = list(
            chain.from_iterable(
                exchange_graph.get_edges(
                    token_in = token_in,
                    token_out = token_out
                )
                for token_in in exchange_graph.tokens
                for token_out in exchange_graph.tokens
                if token_in != token_out
            )
        )

        quote_function_meta_list: List[QuoteFunctionMeta] = [
            edge.get_quote_function_meta(
                amount_in = amount_in_dict.get(edge.token_in),
                block_identifier = block_number
            )
            for edge in edges
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

        for edge, amount_out in zip(edges, amount_out_list):
            quote_graph.add_edge(
                edge.token_in, edge.token_out, edge, **asdict(Quote(
                    token_in = edge.token_in,
                    token_out = edge.token_out,
                    amount_in = amount_in_dict.get(edge.token_in),
                    amount_out = amount_out
                ))
            )
        
        return quote_graph


    def __find_arbitrages_naive(
        self, exchange_graph: ExchangeGraph, hops: int,
        token_in: ChecksumAddress, amount_in: int,
        curr_path: Path, block_number: BlockNumber
    ) -> Generator[Arbitrage, None, None]:  
        curr_token_in: ChecksumAddress = curr_path[-1].exchange_edge.token_out if curr_path else token_in
        curr_amount_in: int = curr_path[-1].amount_out if curr_path else amount_in

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
                callbacks = [ 
                    edge.get_quote_function_meta(
                        amount_in = curr_amount_in,
                        block_identifier = block_number
                    ).callback
                    for edge in edges
                ]
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
                    yield Arbitrage(
                        path = deepcopy(curr_path),
                        expected_gas = 0, # TODO implement expected gas
                        block_number = block_number
                    )
                curr_path.pop()
        else:
            edges: List[ExchangeEdge] = list(
                chain.from_iterable(
                    exchange_graph.get_edges(
                        token_in = curr_token_in,
                        token_out = next_token
                    )
                    for next_token in exchange_graph.tokens
                    if next_token not in curr_path and curr_token_in != next_token
                )
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
                callbacks = [ 
                    edge.get_quote_function_meta(
                        amount_in = curr_amount_in,
                        block_identifier = block_number
                    ).callback
                    for edge in edges
                ]
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
                yield from self.__find_arbitrages_naive(
                    exchange_graph = exchange_graph,
                    hops = hops - 1,
                    token_in = token_in,
                    amount_in = amount_in,
                    curr_path = deepcopy(curr_path),
                    block_number = block_number
                )
                curr_path.pop()
    

    def evaluate_arbitrage(
        self: Self, path_meta: List[ExchangeEdge], amount_in: int,
        block_number: BlockNumber, only_profitable: bool = True
    ) -> Optional[Arbitrage]:
        path: Path = Path()
        block_number: BlockNumber = block_number

        curr_amount: int = amount_in
        for edge in path_meta:
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

        if (
            not only_profitable
            or curr_amount > amount_in # Profitable
        ):
            return Arbitrage(
                path = path,
                block_number = block_number,
                expected_gas = 0 # TODO implement expected gas
            )
    
        return None


    # def optimize_arbitrage_naive_sync(
    #     self: Self, arbitrage: Arbitrage
    # ) -> Arbitrage:
    #     '''
    #     Search for the optimal input amount around the given input amount
    #     '''
    #     path_meta: List[ExchangeEdge] = [hop.exchange_edge for hop in arbitrage.path]

    #     amount_in_multipliers: List[float] = numpy.arange(0.1, 10.1, 0.1)

    #     best_arbitrage: Arbitrage = arbitrage
    #     for amount_in_multiplier in amount_in_multipliers:
    #         amount_in: int = int(amount_in_multiplier * arbitrage.amount_in)

    #         new_arbitrage: Optional[Arbitrage] = self.evaluate_arbitrage(
    #             path_meta = path_meta,
    #             amount_in = amount_in,
    #             block_number = arbitrage.block_number
    #         )

    #         if new_arbitrage is None:
    #             continue

    #         if new_arbitrage.profit > best_arbitrage.profit:
    #             best_arbitrage = new_arbitrage

    #     return best_arbitrage


    # def optimize_arbitrage_naive_async(
    #     self: Self, arbitrage: Arbitrage
    # ) -> Arbitrage:
    #     '''
    #     Search for the optimal input amount around the given input amount
    #     '''
    #     path_meta: List[ExchangeEdge] = [hop.exchange_edge for hop in arbitrage.path]

    #     amount_in_multipliers: List[float] = numpy.arange(0.1, 10.1, 0.1)

    #     best_arbitrage: Arbitrage = arbitrage
    #     with ThreadPool() as pool:
    #         new_arbitrage: Optional[Arbitrage] = max(
    #             pool.map(
    #                 func = lambda amount_in_multiplier: self.evaluate_arbitrage(
    #                     path_meta = path_meta,
    #                     amount_in = int(amount_in_multiplier * arbitrage.amount_in),
    #                     block_number = arbitrage.block_number
    #                 ),
    #                 iterable = amount_in_multipliers
    #             ),
    #             key = lambda arbitrage: (
    #                 arbitrage.profit if arbitrage is not None else -float("inf")
    #             )
    #         )

    #         if (
    #             new_arbitrage is not None
    #             and new_arbitrage.profit > best_arbitrage.profit
    #         ):
    #             best_arbitrage = new_arbitrage

    #     return best_arbitrage


    # # TODO Try very large input amount and get the output amount.
    # # Use this output amount to get the input amount
    # def __optimize_arbitrage_chain(
    #     self: Self, arbitrage: Arbitrage
    # ) -> Arbitrage:
    #     path_meta: List[ExchangeEdge] = [hop.exchange_edge for hop in arbitrage.path]
        
    #     best_arbitrage: Arbitrage = None

    #     curr_input_amount: int = int(1e36)