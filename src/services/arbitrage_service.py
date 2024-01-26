from .contract_service import ContractService
from .price_feed_service import PriceFeedService

from ..data_structures.exchange_graph import QuoteFunctionMeta, ExchangeEdge, ExchangeGraph
from ..data_structures.quote_graph import Quote, QuoteGraph
from ..data_structures.arbitrage import Hop, Path, Arbitrage
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from eth_typing.evm import ChecksumAddress, BlockNumber, BlockIdentifier

from copy import deepcopy
from typing import (
    Dict,
    List,
)
from typing_extensions import Self
from dataclasses import asdict

class ArbitrageService():
    def __init__(self: Self, w3: Web3) -> None:
        self.w3: Web3 = w3

        self.contract_service: ContractService = ContractService(
            w3 = self.w3
        )
        self.price_feed_service: PriceFeedService = PriceFeedService(
            w3 = self.w3
        )

    
    def find_arbitrages_naive(
        self: Self, exchange_graph: ExchangeGraph,
        max_hops: int, block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        arbitrages: List[Arbitrage] = []
        
        base_fee_per_gas: int = self.contract_service.get_base_fee_per_gas(
            block_identifier = block_number
        )
        test_exposure_eth: float = base_fee_per_gas * 1e6
        token_prices_eth: Dict[ChecksumAddress, int] = self.price_feed_service.fetch_price_eth(
            tokens = exchange_graph.tokens,
            block_identifier = block_number
        )

        for token_in in exchange_graph.tokens:
            amount_in: int = round(
                test_exposure_eth * token_prices_eth.get(token_in) * 1e18
            )
            for hops in range(2, max_hops + 1):
                arbitrages.extend(
                    self.__find_arbitrages_naive(
                        exchange_graph = exchange_graph,
                        hops = hops,
                        token_in = token_in,
                        amount_in = amount_in,
                        curr_path = Path(),
                        block_number = block_number
                    )
                )
        
        return arbitrages


    def find_arbitrages_bellman_ford(
        self: Self, exchange_graph: ExchangeGraph,
        max_hops: int, block_identifier: BlockIdentifier = "latest"
    ) -> List[Arbitrage]:
        assert max_hops > 1, f"At least 2 hops are needed for an arbitrage. Given max_hops = {max_hops}."
        
        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        # TODO Make u_eth an input parameter instead
        base_fee_per_gas: int = self.contract_service.get_base_fee_per_gas(
            block_identifier = block_number
        )
        u_eth: float = base_fee_per_gas * 1e6

        quote_graph: QuoteGraph = self.__construct_quote_graph(
            exchange_graph = exchange_graph,
            u_eth = u_eth,
            block_number = block_number
        )

        arbitrages: List[Arbitrage] = []
        path_meta_list = quote_graph.find_potential_arbitrage_path_meta()
        for path_meta in path_meta_list:
            path: Path = Path()
            amount_in: int = quote_graph.get_quote(
                path_meta[0]
            ).amount_in
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
                    quote_graph.add_edge(
                        token_in, token_out, edge, **asdict(Quote(
                            token_in = token_in,
                            token_out = token_out,
                            amount_in = amount_in,
                            amount_out = amount_out
                        ))
                    )
        return quote_graph


    def __find_arbitrages_naive(
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
                    arbitrages.append(
                        Arbitrage(
                            path = deepcopy(curr_path),
                            expected_gas = 0, # TODO implement expected gas
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
                arbitrages.extend(
                    self.__find_arbitrages_naive(
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