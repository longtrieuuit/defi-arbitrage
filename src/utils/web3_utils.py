from web3 import Web3
from eth_typing.evm import ChecksumAddress, BlockNumber, BlockIdentifier

def block_identifier_to_number(w3: Web3, block_identifier: BlockIdentifier) -> BlockNumber:
    return (
        block_identifier if isinstance(block_identifier, int)
        else w3.eth.get_block_number()
    )