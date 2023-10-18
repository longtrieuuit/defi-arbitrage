import pandas as pd

import re
from io import TextIOWrapper

def parse_log(log_io: TextIOWrapper, log_pattern: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            key: value
            for key, value in zip(
                ["time", "level", "msg", "error", "tx", "input"],
                re.search(log_pattern, line.rstrip()).groups()
            )
        }
        for line in log_io.readlines()
    )

if __name__ == "__main__":
    with open("tx_without_input.log") as f:
        ankr_log_pattern: str = r'time="([^"]+)" level=([^ ]+) msg=([^ ]+)(?: error="([^"]*)")?(?: tx=([^ ]+))?(?: input=([^ ]+))?'
        log_df: pd.DataFrame = parse_log(f, ankr_log_pattern)
        log_df.to_csv("ankr_data.csv", index = False)