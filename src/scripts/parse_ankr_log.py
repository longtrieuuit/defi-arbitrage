from ..utils.log_parser import parse_log

import pandas as pd

if __name__ == "__main__":
    with open("tx_without_input.log") as f:
        ankr_log_pattern: str = r'time="([^"]+)" level=([^ ]+) msg=([^ ]+)(?: error="([^"]*)")?(?: tx=([^ ]+))?(?: input=([^ ]+))?'
        log_df: pd.DataFrame = parse_log(f, ankr_log_pattern)
        log_df.to_csv("data/ankr_data.csv", index = False)