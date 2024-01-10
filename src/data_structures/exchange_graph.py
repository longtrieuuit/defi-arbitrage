from .call import Call, CallReturn

from web3.types import TxParams
from eth_typing.evm import ChecksumAddress, BlockIdentifier

from dataclasses import dataclass
from typing_extensions import Self
from typing import (
    Dict,
    List,
    Callable,
    Protocol,
    NewType
)


@dataclass(frozen = True)
class QuoteFunctionMeta():
    call: Call
    callback: Callable[[CallReturn], int]


class QuoteFunctionType(Protocol):
    def __call__(
        self: Self, token_in: ChecksumAddress, token_out: ChecksumAddress,
        amount_in: int, block_identifier: BlockIdentifier = "latest"
    ) -> QuoteFunctionMeta:
        ...


class SwapFuncionType(Protocol):
    def __call__(
        self: Self, token_in: ChecksumAddress, token_out, ChecksumAddress,
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
        self: Self, amount_in: int, block_identifier: BlockIdentifier = "latest"
    ) -> QuoteFunctionMeta:
        return self.exchange_function.quote_function(
            token_in = self.token_in,
            token_out = self.token_out,
            amount_in = amount_in,
            block_identifier = block_identifier
        )
    
    def create_transaction(
        self: Self, amount_in: int, wallet_address: ChecksumAddress,
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
        self: Self, tokens: List[ChecksumAddress], exchange_functions: List[ExchangeFunction]
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
        self: Self, token_in: ChecksumAddress, token_out: ChecksumAddress
    ) -> List[ExchangeEdge]:
        return self.exchange_edge_dict.get(token_in).get(token_out)