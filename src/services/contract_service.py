from ..data_structures.call import Call, CallReturn
from ..utils.abi import get_abi
from ..utils.web3_utils import block_identifier_to_number

from web3 import Web3
from web3.contract import Contract
from web3.types import TxParams, Wei
from eth_typing.evm import ChecksumAddress, BlockIdentifier, BlockNumber
from eth_abi import decode

from multiprocessing.pool import ThreadPool
from itertools import chain
from typing import Dict, Any, List, Tuple, Optional, Union, Callable


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
        callbacks: Optional[List[Callable[[CallReturn], Any]]] = None
    ) -> List[Any]:
        if callbacks is not None:
            assert len(calls) == len(callbacks), (
                f"Length mismatch between calls ({len(calls)}) and callbacks ({len(callbacks)})."
            )

        calls: List[Call] = self.__prepare_calls(calls = calls)

        multicall_result: List[CallReturn] = self.__multicall(
            calls = calls,
            require_success = require_success,
            block_identifier = block_identifier,
            chunk_size = max(1, len(calls) // 4)
        )

        if callbacks is None:
            return multicall_result
        
        return list(map(
            lambda x: x[0](x[1]), zip(
                callbacks, multicall_result
            )
        ))
    

    def batch_call_simple(
        self, calls: List[Union[Call, Dict[str, Any]]],
        require_success: bool = True, block_identifier: BlockIdentifier = "latest",
        callbacks: Optional[List[Callable[[CallReturn], Any]]] = None
    ) -> List[Any]:
        if callbacks is not None:
            assert len(calls) == len(callbacks), (
                f"Length mismatch between calls ({len(calls)}) and callbacks ({len(callbacks)})."
            )

        calls: List[Call] = self.__prepare_calls(calls = calls)

        results: List[CallReturn] = self.__batch_call_simple(
            calls = calls,
            require_success = require_success,
            block_identifier = block_identifier
        )

        if callbacks is None:
            return results

        return list(map(
            lambda x: x[0](x[1]), zip(
                callbacks, results
            )
        ))
    
    
    def batch_call_multithreading(
        self, calls: List[Union[Call, Dict[str, Any]]],
        require_success: bool = True, block_identifier: BlockIdentifier = "latest",
        callbacks: Optional[List[Callable[[CallReturn], Any]]] = None
    ) -> List[Any]:
        if callbacks is not None:
            assert len(calls) == len(callbacks), (
                f"Length mismatch between calls ({len(calls)}) and callbacks ({len(callbacks)})."
            )

        calls: List[Call] = self.__prepare_calls(calls = calls)

        results: List[CallReturn] = self.__batch_call_multithreading(
            calls = calls,
            require_success = require_success,
            block_identifier = block_identifier
        )

        if callbacks is None:
            return results

        return list(map(
            lambda x: x[0](x[1]), zip(
                callbacks, results
            )
        ))
        

    def estimate_gas(self, transaction: TxParams, block_identifier: BlockIdentifier = "latest") -> Wei:
        return self.w3.eth.estimate_gas(
            transaction = transaction,
            block_identifier = block_identifier
        )
    

    def __prepare_calls(self, calls: List[Union[Call, Dict[str, Any]]]) -> List[Call]:
        calls: List[Call] = [call if isinstance(call, Call) else Call(**call) for call in calls]
        for call in calls:
            if call.contract_address not in self.contract_cache:
                if call.contract_abi is None:
                    raise Exception(
                        f"Contract {call.contract_address} is never called. Use add_contract() to add the contract or specify the ABI to the Call object."
                    )
                self.add_contract(
                    address = call.contract_address,
                    abi = call.contract_abi
                )
        return calls
    

    def __batch_call_simple(
        self, calls: List[Call], require_success: bool = True,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[CallReturn]:
        return [
            self.__try_call_helper(
                call = call,
                require_success = require_success,
                block_identifier = block_identifier
            )
            for call in calls
        ]


    def __batch_call_multithreading(
        self, calls: List[Call], require_success: bool = True,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[CallReturn]:
        results: List[CallReturn] = []
        with ThreadPool() as pool:
            results = pool.map(
                func = lambda call: self.__try_call_helper(
                    call = call,
                    require_success = require_success,
                    block_identifier = block_identifier
                ),
                iterable = calls
            )
        return results
        

    def __try_call_helper(
        self, call: Call, require_success: bool = True,
        block_identifier: BlockIdentifier = "latest"
    ) -> CallReturn:
        try:
            call_return_data: Any = self.get_contract(
                address = call.contract_address,
                abi = call.contract_abi
            ).get_function_by_name(
                call.function_name
            )(
                *call.args
            ).call(
                block_identifier = block_identifier
            )

            return CallReturn(
                success = True,
                return_data = (call_return_data, ) if len(call.output_types) == 1 else call_return_data
            )
        except Exception as e:
            if require_success:
                raise e
            
            return CallReturn(
                success = False,
                return_data = None
            )


    def __multicall(
        self, calls: List[Call], require_success: bool = True,
        block_identifier: BlockIdentifier = "latest",
        chunk_size: int = 5
    ) -> List[CallReturn]:
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

        encoded_call_chunks: List[List[Tuple[ChecksumAddress, str]]] = [
            encoded_calls[i: i + chunk_size]
            for i in range(0, len(encoded_calls), chunk_size)
        ]

        encoded_results: List[CallReturn] = []
        with ThreadPool() as pool:
            encoded_results = list(
                chain.from_iterable(
                    pool.map(
                        func = lambda encoded_call_chunk: self.multicall_contract.functions.tryAggregate(
                            require_success,
                            encoded_call_chunk
                        ).call(
                            block_identifier = block_identifier
                        ),
                        iterable = encoded_call_chunks
                    )
                )
            )
        
        return [
            CallReturn(
                success = encoded_result[0],
                return_data = decode(call.output_types, encoded_result[1])
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
