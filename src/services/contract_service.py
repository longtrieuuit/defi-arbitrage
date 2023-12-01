from ..utils.abi import get_abi
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from web3.contract import Contract
from web3.types import TxParams, Wei
from eth_typing.evm import ChecksumAddress, BlockIdentifier, BlockNumber
from eth_abi import decode_abi

from typing import Dict, Any, List, Tuple, Iterable, Optional, Union, Callable
from dataclasses import dataclass

@dataclass
class Call:
    contract_address: ChecksumAddress
    function_name: str
    args: List[Any]
    output_types: List[str]
    contract_abi: Optional[Any] = None


@dataclass
class MulticallReturnData:
    success: bool
    return_data: Optional[Iterable[Any]] = None


class ContractService:
    MULTICALL_ADDRESS: ChecksumAddress = "0x5BA1e12693Dc8F9c48aAD8770482f4739bEeD696"

    def __init__(self, w3: Web3) -> None:
        self.w3: Web3 = w3
        self.contract_cache: Dict[ChecksumAddress, Contract] = dict()
        self.multicall_contract: Contract = self.__call_contract(
            address = ContractService.MULTICALL_ADDRESS,
            abi = get_abi("multicall2")
        )

        self.base_fee_history: Dict[BlockNumber, int] = dict()
    

    def add_contract(self, address: ChecksumAddress, abi: Any) -> None:
        if address not in self.contract_cache:
            self.__call_contract(address = address, abi = abi)
        return None


    def get_contract(self, address: ChecksumAddress, abi: Any = None) -> Contract:
        if address in self.contract_cache:
            return self.contract_cache[address]
        
        if abi is None:
            raise Exception(f"Contract {address} is not found in cache while ABI is not specified")
        
        return self.__call_contract(address = address, abi = abi)
    

    def get_base_fee_per_gas(self, block_identifier: BlockIdentifier = "latest") -> int:
        block_number: int = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        if block_number in self.base_fee_history:
            return self.base_fee_history.get(block_number)
        
        base_fee_per_gas_raw: List[int] = self.w3.eth.fee_history(
            block_count = 1,
            newest_block = block_number
        )["baseFeePerGas"]

        self.base_fee_history[block_number] = base_fee_per_gas_raw[0]
        self.base_fee_history[block_number + 1] = base_fee_per_gas_raw[1]

        return self.base_fee_history[block_number]
      
    
    def multicall(
        self, calls: List[Union[Call, Dict[str, Any]]],
        require_success: bool = True, block_identifier: BlockIdentifier = "latest",
        callbacks: Optional[List[Callable[[MulticallReturnData], Any]]] = None
    ) -> List[Any]:
        if callbacks is not None:
            assert len(calls) == len(callbacks), (
                f"Length mismatch between calls ({len(calls)}) and callbacks ({len(callbacks)})."
            )

        calls_copy: List[Call] = [call if isinstance(call, Call) else Call(**call) for call in calls]
        for call in calls_copy:
            if call.contract_address not in self.contract_cache:
                if call.contract_abi is None:
                    raise Exception(
                        f"Contract {call['contract_address']} is never called. Use add_contract() to add the contract or specify the ABI to the Call object."
                    )
                self.add_contract(
                    address = call.contract_address,
                    abi = call.contract_abi
                )

        multicall_result: List[MulticallReturnData] = self.__multicall(
            calls = calls_copy,
            require_success = require_success,
            block_identifier = block_identifier
        )

        if callbacks is None:
            return multicall_result
        
        return list(map(
            lambda x: x[0](x[1]), zip(
                callbacks, multicall_result
            )
        ))
    

    def estimate_gas(self, transaction: TxParams, block_identifier: BlockIdentifier = "latest") -> Wei:
        return self.w3.eth.estimate_gas(
            transaction = transaction,
            block_identifier = block_identifier
        )
    

    def __multicall(
        self, calls: List[Call], require_success: bool = True,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[MulticallReturnData]:
        encoded_calls: List[Tuple[ChecksumAddress, str]] = [
            (
                call.contract_address,
                self.get_contract(call.contract_address).encodeABI(
                    fn_name = call.function_name,
                    args = call.args
                )
            )
            for call in calls
        ]

        encoded_results = self.multicall_contract.functions.tryAggregate(require_success, encoded_calls).call(
            block_identifier = block_identifier
        )
        
        return [
            MulticallReturnData(
                success = encoded_result[0],
                return_data = decode_abi(call.output_types, encoded_result[1])
                    if encoded_result[0] else None
            )
            for call, encoded_result in zip(calls, encoded_results)
        ]


    def __call_contract(self, address: ChecksumAddress, abi: Any, cache: bool = True) -> Contract:
        contract: Contract = self.w3.eth.contract(
            address = address,
            abi = abi
        )

        if cache:
            self.contract_cache[address] = contract
        
        return contract
