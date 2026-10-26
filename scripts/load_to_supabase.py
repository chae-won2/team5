"""data/processed/*.csv 를 Supabase 테이블에 업로드한다.

모든 테이블이 deterministic id를 PK로 쓰고, upsert(on_conflict="id")로 적재하므로
몇 번을 다시 실행해도 같은 행이 같은 id로 덮어써질 뿐 중복이 쌓이지 않는다 (멱등성).

사전 준비: supabase/schema.sql 을 Supabase SQL Editor에서 한 번 실행해서 테이블을 만들어둘 것.
.env 에 SUPABASE_URL, SUPABASE_SERVICE_KEY 필요.
"""

import math
import os

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

OUT_DIR = "data/processed"
BATCH_SIZE = 500

TABLES = ["merchants", "tourist_spots", "consumption", "visitors", "commercial_density"]


def clean_record(d):
    # NaN은 JSON으로 못 보내니 None으로 치환
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in d.items()}


def load_table(client, table_name):
    path = os.path.join(OUT_DIR, f"{table_name}.csv")
    if not os.path.exists(path):
        path = os.path.join(OUT_DIR, "bin", f"{table_name}.csv")
    if not os.path.exists(path):
        print(f"스킵 (파일 없음): {path}")
        return

    df = pd.read_csv(path, encoding="utf-8-sig")
    records = [clean_record(r) for r in df.to_dict(orient="records")]

    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        client.table(table_name).upsert(batch, on_conflict="id").execute()
        print(f"  {table_name}: {i + len(batch)}/{len(records)}")

    print(f"완료: {table_name} ({len(records)}행 upsert)")


def main():
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    for table_name in TABLES:
        load_table(client, table_name)


if __name__ == "__main__":
    main()
