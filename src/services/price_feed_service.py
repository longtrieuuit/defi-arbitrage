from ..services.contract_service import ContractService
from ..utils.abi import get_abi

from web3 import Web3
from eth_typing.evm import ChecksumAddress, BlockIdentifier

from typing import Any, Dict, List

class PriceFeedService():
    '''
    Price feed service using 1inch spot price aggregator
    '''
    SPOT_AGGREGATOR_1INCH_ADDRESS: ChecksumAddress = "0x0AdDd25a91563696D8567Df78D5A01C9a991F9B8"
    SPOT_AGGREGATOR_1INCH_ABI: Any = get_abi(abi_name = "spot_aggregator_1inch")

    USD_PROXY_ADDRESS: ChecksumAddress = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48" # USDC
    ERC20_ABI: Any = get_abi(abi_name = "erc20")

    def __init__(self, w3: Web3) -> None:
        self.w3: Web3 = w3

        self.contract_service: ContractService = ContractService(
            w3 = self.w3
        )

        self.contract_service.add_contract(
            address = self.SPOT_AGGREGATOR_1INCH_ADDRESS,
            abi = self.SPOT_AGGREGATOR_1INCH_ABI
        )
        
        self.contract_service.add_contract(
            address = self.USD_PROXY_ADDRESS,
            abi = self.ERC20_ABI
        )

    def fetch_eth_price_usd(self, block_identifier: BlockIdentifier) -> float:
        return 1e-6 / self.fetch_price_eth(
            tokens = [self.USD_PROXY_ADDRESS],
            block_identifier = block_identifier
        )[self.USD_PROXY_ADDRESS]


    def fetch_price_eth(self, tokens: List[ChecksumAddress], block_identifier: BlockIdentifier) -> Dict[ChecksumAddress, float]:
        return {
            token_address: price_to_eth / 1e36
            for token_address, price_to_eth in zip(
                tokens, map(
                    lambda result: result.return_data[0] if result.success else None,
                    self.contract_service.multicall(
                        calls = [
                            {
                                "contract_address": self.SPOT_AGGREGATOR_1INCH_ADDRESS,
                                "function_name": "getRateToEth",
                                "args": [
                                    token_address,
                                    True
                                ],
                                "output_types": [
                                    "uint256"
                                ]
                            }
                            for token_address in tokens
                        ],
                        require_success = True,
                        block_identifier = block_identifier
                    )
                )
            )
        }
    

    def fetch_price_usd(self, tokens: List[ChecksumAddress], block_identifier: BlockIdentifier) -> Dict[ChecksumAddress, float]:
        eth_price_usd: float = self.fetch_eth_price_usd(
            block_identifier = block_identifier
        )

        token_decimals: Dict[ChecksumAddress, int] = self.fetch_token_decimals(
            tokens = tokens,
            block_identifier = block_identifier
        )

        return {
            token_address: (
                price_eth
                * eth_price_usd
                * 10 ** token_decimals.get(token_address)
            ) if price_eth is not None else None
            for token_address, price_eth in self.fetch_price_eth(
                tokens = tokens,
                block_identifier = block_identifier
            ).items()
        }

    def fetch_token_decimals(
        self, tokens: List[ChecksumAddress], block_identifier: BlockIdentifier = "latest"
    ) -> Dict[ChecksumAddress, float]:
        self.__initialize_token_contracts(tokens = tokens)
        return {
            token_address: decimals
            for token_address, decimals in zip(
                tokens,
                map(
                    lambda result: result.return_data[0] if result.success else None,
                    self.contract_service.multicall(
                        calls = [
                            {
                                "contract_address": token_address,
                                "function_name": "decimals",
                                "args": [],
                                "output_types": [
                                    "uint256"
                                ]
                            }
                            for token_address in tokens
                        ],
                        require_success = True,
                        block_identifier = block_identifier
                    )
                )
            )
        }

    def __initialize_token_contracts(
        self, tokens: List[ChecksumAddress]
    ) -> None:
        for token_address in tokens:
            self.contract_service.add_contract(
                address = token_address,
                abi = self.ERC20_ABI
            )