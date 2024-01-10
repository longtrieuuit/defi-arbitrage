from .exchange_graph import ExchangeEdge

from eth_typing.evm import ChecksumAddress

from dataclasses import dataclass, field
from math import log2
from typing import (
    Dict,
    NewType
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