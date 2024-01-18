from eth_typing.evm import ChecksumAddress

from typing import Any, List, Iterable, Optional
from dataclasses import dataclass

@dataclass
class Call:
    contract_address: ChecksumAddress
    function_name: str
    args: List[Any]
    output_types: List[str]
    contract_abi: Optional[Any] = None


@dataclass
class CallReturn:
    success: bool
    return_data: Optional[Iterable[Any]] = None
