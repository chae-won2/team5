"""data/raw/bin/csv/*.csv 파일들을 모두 읽어 하나로 합쳐 data/processed/bin/merged.csv로 저장."""

import glob
import os

import pandas as pd

RAW_DIR = "data/raw/bin/csv"
OUTPUT_PATH = "data/processed/bin/merged.csv"


def load_raw_files():
    paths = glob.glob(os.path.join(RAW_DIR, "*.csv"))
    dfs = []
    for path in paths:
        df = pd.read_csv(path)
        df["source_file"] = os.path.basename(path)
        dfs.append(df)
    return dfs


def main():
    dfs = load_raw_files()
    if not dfs:
        print(f"{RAW_DIR}에 csv 파일이 없습니다.")
        return

    merged = pd.concat(dfs, ignore_index=True)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    merged.to_csv(OUTPUT_PATH, index=False)
    print(f"{len(dfs)}개 파일을 합쳐 {OUTPUT_PATH}에 저장했습니다. (총 {len(merged)}행)")


if __name__ == "__main__":
    main()
