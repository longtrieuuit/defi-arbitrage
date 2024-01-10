from .exchange_service import ExchangeService
from .contract_service import ContractService
from .price_feed_service import PriceFeedService
from .thegraph_service import TheGraphService

from ..data_structures.call import Call, CallReturn
from ..data_structures.exchange_graph import QuoteFunctionMeta, ExchangeFunction
from ..utils.web3_utils import block_identifier_to_number
from ..utils.abi import get_abi

from web3 import Web3
from web3.contract.contract import Contract, ContractFunction
from web3.types import TxParams
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_typing.evm import ChecksumAddress, BlockIdentifier, BlockNumber

from hexbytes import HexBytes
from typing import Any, List, Callable
from typing_extensions import Self


class UniswapV2Service(ExchangeService):
    # Router
    ROUTER_ADDRESS: ChecksumAddress = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
    ROUTER_ABI: Any = get_abi("uniswapv2_router02")

    # Factory
    FACTORY_ADDRESS: ChecksumAddress = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
    FACTORY_ABI: Any = get_abi("uniswapv2_factory")

    # ERC20
    ERC20_ABI: Any = get_abi("erc20")

    def __init__(self: Self, w3: Web3, executor_private_key: HexBytes) -> None:
        print("Initializing UniswapV2 Service")

        self.w3: Web3 = w3
        self.executor: LocalAccount = Account.from_key(executor_private_key)

        self.contract_service: ContractService = ContractService(w3 = self.w3)
        self.price_feed_service: PriceFeedService = PriceFeedService(w3 = self.w3)
        self.thegraph_service: TheGraphService = TheGraphService()

        self.router: Contract = self.contract_service.get_contract(
            address = self.ROUTER_ADDRESS,
            abi = self.ROUTER_ABI
        )

        self.factory: Contract = self.contract_service.get_contract(
            address = self.FACTORY_ADDRESS,
            abi = self.FACTORY_ABI
        )

    
    def get_exchange_functions(self: Self, block_identifier: BlockIdentifier = "latest") -> List[ExchangeFunction]:
        quote_callback: Callable[[CallReturn], int] = lambda result: (
            result.return_data[0][1] if result.success else 0
        )

        block_number: BlockNumber = block_identifier_to_number(
            w3 = self.w3,
            block_identifier = block_identifier
        )

        next_block_time: int = self.w3.eth.get_block(
            block_identifier = block_number + 1
        ).get("timestamp")

        return [
            ExchangeFunction(
                quote_function = lambda token_in, token_out, amount_in, block_identifier: QuoteFunctionMeta(
                    call = Call(
                        contract_address = self.ROUTER_ADDRESS,
                        function_name = "getAmountsOut",
                        args = [
                            amount_in,
                            [token_in, token_out]
                        ],
                        output_types = [
                            "uint256[]"
                        ],
                        contract_abi = self.ROUTER_ABI
                    ),
                    callback = quote_callback
                ),
                swap_function = lambda token_in, token_out, amount_in, wallet_address, block_identifier: (
                    self.swap_exact_input(
                        amount_in = amount_in,
                        amount_out_minimum = amount_in,
                        path = [token_in, token_out],
                        recipient = wallet_address,
                        deadline = next_block_time,
                        block_identifier = block_number
                    )
                )
            )
        ]

    
    def swap_exact_input(
        self, amount_in: int, amount_out_minimum: int,
        path: List[ChecksumAddress], recipient: ChecksumAddress,
        deadline: int, block_identifier: BlockIdentifier = "latest"
    ) -> TxParams:
        swap_func: ContractFunction = self.router.get_function_by_name("swapExactTokensForTokens")(
            amount_in,
            amount_out_minimum,
            path,
            recipient,
            deadline
        )

        # print(swap_func.estimate_gas(
        #     transaction = {
        #         "from": recipient
        #     },
        #     block_identifier = block_identifier
        # ))

        return swap_func.build_transaction()
