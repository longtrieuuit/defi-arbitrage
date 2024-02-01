from .exchange_graph import ExchangeEdge

from eth_typing.evm import ChecksumAddress, BlockNumber

from dataclasses import dataclass, field
from typing import (
    Any,
    List,
    Iterable,
    SupportsIndex
)
from typing_extensions import Self


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
        assert (
            self.__len__() == 0
            or self.__getitem__(-1).exchange_edge.token_out == __object.exchange_edge.token_in
        ), f"New hop's input token (given {__object.exchange_edge.token_in}) must be the same as the last hop's output token ({self.__getitem__(-1).exchange_edge.token_out})."
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

    @property
    def profit(self) -> int:
        return self.amount_out - self.amount_in
    
    def is_profitable(self) -> bool:
        return self.profit > 0
