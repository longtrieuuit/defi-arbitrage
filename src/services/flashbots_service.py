from web3 import Web3
from web3.exceptions import TransactionNotFound
from flashbots import flashbot
from flashbots.flashbots import FlashbotsBundleTx, FlashbotsBundleRawTx, FlashbotsBundleResponse
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from typing import List, Union, Optional

from uuid import uuid4

class FlashbotsService:
    def __init__(self, w3: Web3, bundle_relay_url: str) -> None:
        self.w3: Web3 = w3
        self.eth_signature_account: LocalAccount = Account.create()
        self.bundle_relay_url: str = bundle_relay_url
        flashbot(
            w3 = self.w3,
            signature_account = self.eth_signature_account,
            endpoint_uri = self.bundle_relay_url
        )
        
    def send_bundle(
        self,
        bundle: List[Union[FlashbotsBundleTx, FlashbotsBundleRawTx]],
        max_number_of_attempts: int = 10
    ) -> Optional[FlashbotsBundleResponse]: 
        for attempt in range(max_number_of_attempts):
            print("Attempt:", attempt + 1)
            send_bundle: FlashbotsBundleResponse = self.__attempt_send_bundle(
                bundle = bundle
            )
            if send_bundle is not None:
                break
        
        return send_bundle

    def __attempt_send_bundle(
        self,
        bundle: List[Union[FlashbotsBundleTx, FlashbotsBundleRawTx]]
    ) -> FlashbotsBundleResponse:
        # Get current block number
        block_number: int = self.w3.eth.block_number

        # Simulate bundle on current block
        print(f"Simulating on block {block_number}")
        try:
            sim_res = self.w3.flashbots.simulate(bundle, block_number)
            print("Simulation successful.")
        except Exception as e:
            print("Simulation error", e)
            return
        
        # Send bundle targeting next block
        print(f"Sending bundle targeting block {block_number + 1}")
        replacement_uuid = str(uuid4())
        print(f"replacementUuid {replacement_uuid}")
        send_result = self.w3.flashbots.send_bundle(
            bundle,
            target_block_number = block_number + 1,
            opts={"replacementUuid": replacement_uuid},
        )
        print("Bundle Hash\n", self.w3.toHex(send_result.bundle_hash()))

        bundle_stats = self.w3.flashbots.get_bundle_stats_v2(
            self.w3.toHex(send_result.bundle_hash()), block_number
        )
        print("Bundle Stats\n", bundle_stats)

        send_result.wait()

        try:
            receipts = send_result.receipts()
            print(f"\nBundle was mined in block {receipts[0].blockNumber}\a")
            return send_result
        except TransactionNotFound:
            print(f"Bundle not found in block {block_number+1}")
            # essentially a no-op but it shows that the function works
            cancel_res = self.w3.flashbots.cancel_bundles(replacement_uuid)
            print(f"canceled {cancel_res}")
            return None