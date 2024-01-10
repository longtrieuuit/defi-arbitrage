from ..data_structures.exchange_graph import ExchangeFunction

from eth_typing.evm import BlockIdentifier

from abc import ABC, abstractmethod
from typing import List
from typing_extensions import Self

class ExchangeService(ABC):

    @abstractmethod
    def get_exchange_functions(self: Self, block_identifier: BlockIdentifier) -> List[ExchangeFunction]:
        pass