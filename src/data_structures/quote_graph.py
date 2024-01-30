from .exchange_graph import ExchangeEdge

from networkx import MultiDiGraph, find_negative_cycle, NetworkXError
from eth_typing.evm import ChecksumAddress

from dataclasses import dataclass, field
from math import log2
from typing import (
    Any,
    Dict,
    List
)


@dataclass
class Quote():
    token_in: ChecksumAddress
    token_out: ChecksumAddress
    amount_in: int
    amount_out: int

    exchange_rate: float = field(init = False)
    negative_log_exchange_rate: float = field(init = False)

    def __post_init__(self) -> None:
        self.exchange_rate = self.amount_out / self.amount_in if self.amount_in != 0 else 0
        self.negative_log_exchange_rate = (
            - log2(self.exchange_rate) if self.exchange_rate > 0 else float("inf")
        )


class QuoteGraph(MultiDiGraph):
    def get_quote(self, exchnage_edge: ExchangeEdge) -> Quote:
        edge_data: Dict[str, Any] = self.get_edge_data(
            u = exchnage_edge.token_in,
            v = exchnage_edge.token_out,
            key = exchnage_edge
        )
        return Quote(
            token_in = edge_data.get("token_in"),
            token_out = edge_data.get("token_out"),
            amount_in = edge_data.get("amount_in"),
            amount_out = edge_data.get("amount_out")
        )

    def find_potential_arbitrage_path_meta(self) -> List[List[ExchangeEdge]]:
        path_meta_list: List[List[ExchangeEdge]] = []
        for source_token in self.nodes:
            try:
                negative_cycle: List[ChecksumAddress] = find_negative_cycle(self, source_token, "negative_log_exchange_rate")
                path_meta: List[ExchangeEdge] = []
                for i in range(len(negative_cycle) - 1):
                    token_in: ChecksumAddress = negative_cycle[i]
                    token_out: ChecksumAddress = negative_cycle[i + 1]
                    edge_data: Dict[ExchangeEdge, Dict[str, Any]] = self.get_edge_data(
                        u = token_in,
                        v = token_out
                    )
                    best_exchange_edge: ExchangeEdge = min(
                        edge_data.items(),
                        key = lambda item: item[1].get("negative_log_exchange_rate")
                    )[0]
                    path_meta.append(best_exchange_edge)
                path_meta_list.append(path_meta)
            except NetworkXError:
                continue
        return path_meta_list