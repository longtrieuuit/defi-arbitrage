from .contract_service import ContractService
from .thegraph_service import TheGraphService

from web3 import Web3
from eth_typing.evm import ChecksumAddress, BlockIdentifier

from datetime import datetime
from functools import cache
from typing import List

class TokenService():
    BITQUERY_THEGRAPH_URL: str = "https://streaming.bitquery.io/graphql"

    def __init__(self, w3: Web3, bitquery_api_key: str) -> None:
        self.w3: Web3 = w3
        self.bitquery_api_key: str = bitquery_api_key

        self.contract_service: ContractService = ContractService(w3 = self.w3)
        self.thegraph_service: TheGraphService = TheGraphService()

    
    @cache
    def fetch_top_token_holders(
        self, token_address: ChecksumAddress, top: int = 5,
        block_identifier: BlockIdentifier = "latest"
    ) -> List[ChecksumAddress]:
        block_timestamp: int = self.w3.eth.get_block(
            block_identifier = block_identifier
        ).get("timestamp")
        date: str = datetime.fromtimestamp(block_timestamp).date()
        
        return list(map(
            lambda item: self.w3.to_checksum_address(item.get("Holder").get("Address")),
            self.thegraph_service.query(
                url = self.BITQUERY_THEGRAPH_URL,
                query = '''
                    {{
                        EVM(dataset: archive, network: eth) {{
                            TokenHolders(
                                date: "{}"
                                tokenSmartContract: "{}"
                                limit: {{count: {}}}
                                orderBy: {{descending: Balance_Amount}}
                            ) {{
                                Holder {{
                                    Address
                                }}
                            }}
                        }}
                    }}
                '''.format(date, token_address, top),
                api_key = self.bitquery_api_key
            ).get("data").get("EVM").get("TokenHolders")
        ))