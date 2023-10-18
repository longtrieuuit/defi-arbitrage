import json
from typing import Any

PATH_TO_ABI_FOLDER: str = "src/abi"

def get_abi(abi_name: str) -> Any:
    try: 
        with open(f"{PATH_TO_ABI_FOLDER}/{abi_name}.json") as f:
            abi: str = json.load(f)
        return abi
    except FileNotFoundError as e:
        print(f"Error: ABI for '{abi_name}' not found")
        return None
