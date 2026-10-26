"""Recheck failed/rejected Kakao matches; keep the original cache untouched."""
import argparse
import csv
import math
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"
DATA_BIN = DATA / "bin"
OUT = DATA_BIN / "kakao_rematch"
FIELDS = ["id", "status", "place_id", "place_name", "category_group_name", "category_name",
          "road_address", "address", "lat", "lon", "distance_m", "name_similarity",
          "address_match", "query", "radius", "reason"]
STOP = threading.Event()
LOCAL = threading.local()


def name_key(value):
    value = re.sub(r"주식회사|유한회사|\(주\)|\(유\)", "", str(value))
    return re.sub(r"[^a-z0-9가-힣]", "", value.lower())


def old_name(value):
    value = re.sub(r"\(.*?\)", "", str(value))
    return re.sub(r"(점|지점|호점)$", "", re.sub(r"[^0-9a-zA-Z가-힣]", "", value))


def address_key(value):
    value = str(value).replace("부산광역시", "부산")
    # Building number is an anchor; floor/unit is deliberately excluded.
    match = re.search(r"([가-힣0-9]+(?:대로|로|길))\s*(\d+(?:-\d+)?)", value)
    return match.groups() if match else None


def distance(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 6371000 * 2 * math.asin(min(1, math.sqrt(h)))


def evaluate(merchant, doc):
    a, b = name_key(merchant.name), name_key(doc.get("place_name", ""))
    similarity = SequenceMatcher(None, a, b).ratio()
    exact = len(a) >= 2 and a == b
    addr = address_key(merchant.address)
    same_address = bool(addr and addr == address_key(doc.get("road_address_name", "")))
    meters = distance(merchant.lat, merchant.lon, float(doc["y"]), float(doc["x"]))
    # Similar names alone cannot establish identity, even when nearby.
    accepted = (exact and (same_address or meters <= 50)) or (same_address and similarity >= .90 and len(a) >= 4)
    return accepted, similarity + .25 * same_address + .10 * exact, similarity, same_address, meters


def fetch(merchant, headers):
    if STOP.is_set():
        return None
    query = re.sub(r"주식회사|유한회사|\(주\)|\(유\)", "", merchant.name).strip()
    street = address_key(merchant.address)
    bare = re.sub(r"\(.*?\)", "", query).strip()  # drop English/transliteration suffix, e.g. "인디프헤어(indiff hair)" -> "인디프헤어"
    searches = [(merchant.name, 100), (query + (" " + street[0] if street else " 부산"), 300), (bare, 500)]
    candidates = {}
    had_error = False
    if not hasattr(LOCAL, "session"):
        LOCAL.session = requests.Session()
    for query, radius in dict.fromkeys(searches):
        for attempt in range(3):
            if STOP.is_set():
                return None
            try:
                response = LOCAL.session.get("https://dapi.kakao.com/v2/local/search/keyword.json",
                    headers=headers, params={"query": query, "x": merchant.lon, "y": merchant.lat,
                    "radius": radius, "size": 15}, timeout=12)
                if response.status_code == 429 or "limit has been exceeded" in response.text.lower():
                    if not STOP.is_set():
                        print(f"API limit reached (HTTP {response.status_code}); saved results can be resumed.", flush=True)
                    STOP.set()
                    return None
                if response.status_code in (401, 403):
                    STOP.set()
                    return {"id": merchant.id, "status": "error", "reason": "authorization"}
                response.raise_for_status()
                docs = response.json().get("documents", [])
                for doc in docs:
                    candidates[doc["id"]] = (doc, query, radius)
                break
            except (requests.RequestException, ValueError):
                if attempt == 2:
                    had_error = True
                else:
                    time.sleep(attempt + 1)
        ranked = sorted([(evaluate(merchant, d), d, q, r) for d, q, r in candidates.values()],
                        key=lambda x: x[0][1], reverse=True)
        if ranked and ranked[0][0][0] and (len(ranked) == 1 or ranked[0][0][1] - ranked[1][0][1] >= .08):
            break
    if not candidates:
        return {"id": merchant.id, "status": "error" if had_error else "no_match", "reason": "no_candidates"}
    ranked = sorted([(evaluate(merchant, d), d, q, r) for d, q, r in candidates.values()],
                    key=lambda x: x[0][1], reverse=True)
    (accepted, score, similarity, same_address, meters), doc, query, radius = ranked[0]
    ambiguous = len(ranked) > 1 and score - ranked[1][0][1] < .08
    return dict(id=merchant.id, status="accepted" if accepted and not ambiguous else "review",
                place_id=doc["id"], place_name=doc["place_name"],
                category_group_name=doc.get("category_group_name", ""), category_name=doc.get("category_name", ""),
                road_address=doc.get("road_address_name", ""), address=doc.get("address_name", ""),
                lat=doc["y"], lon=doc["x"], distance_m=round(meters, 1), name_similarity=round(similarity, 4),
                address_match=same_address, query=query, radius=radius,
                reason="ambiguous" if ambiguous else "identity_rule" if accepted else "needs_verification")


def self_check():
    from types import SimpleNamespace
    m = SimpleNamespace(name="카페가나다", address="부산광역시 중구 중앙대로 10", lat=35.1, lon=129.0)
    d = dict(place_name="카페가나다", road_address_name="부산 중구 중앙대로 10", y="35.1", x="129")
    assert evaluate(m, d)[0]
    assert not evaluate(m, dict(d, place_name="다른카페"))[0]
    assert not evaluate(m, dict(d, place_name="카페가나다 해운대점"))[0]
    assert not evaluate(m, dict(d, y="35.2", road_address_name="중앙대로 12"))[0]
    assert name_key("(주) 가나다 서면점") != name_key("가나다 해운대점")
    assert address_key("부산 중구 중앙대로 10, 2층") != address_key("부산 중구 중앙대로 100")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--districts", nargs="+", help="Prioritize a limited MVP area by address district")
    parser.add_argument("--ids-file", type=Path, help="CSV/text with an 'id' column (or one id per line) to limit the run to")
    parser.add_argument("--retry", action="store_true", help="Reattempt ids even if already present in results.csv as no_match/review (not just error)")
    parser.add_argument("--travel-only", action="store_true", help="Skip known non-tourism search categories and explicit medical/education names")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    self_check()
    if args.self_check:
        print("self-check passed", flush=True)
        return
    load_dotenv(ROOT / ".env")
    headers = {"Authorization": "KakaoAK " + os.environ["KAKAO_REST_API_KEY"]}
    merchants = pd.read_csv(DATA / "merchants.csv")
    cache = pd.read_csv(DATA_BIN / "_kakao_category_cache.csv").drop_duplicates("id", keep="last")
    joined = merchants.merge(cache[["id", "status", "place_name", "category_name"]], on="id", how="left")
    verified_name = pd.Series([len(old_name(n)) >= 2 and old_name(n) == old_name(p) for n, p in zip(joined.name, joined.place_name)], index=joined.index)
    todo = joined[~(joined.status.eq("ok") & verified_name)].copy()
    classified_path = DATA_BIN / "travel_purposes/merchants_travel_purposes.csv"
    if classified_path.exists():
        classified = pd.read_csv(classified_path, usecols=["id", "classification_status"])
        unresolved = classified.loc[classified.classification_status.isin(["unmatched", "review"]), "id"]
        todo = todo[todo.id.isin(unresolved)]
    if args.districts:
        district_pattern = r"(?:^|\s)(?:" + "|".join(re.escape(d) for d in args.districts) + r")(?:\s|$)"
        todo = todo[todo.address.fillna("").str.contains(district_pattern, regex=True)]
    if args.ids_file:
        wanted = pd.read_csv(args.ids_file).id if args.ids_file.suffix == ".csv" else pd.Series(args.ids_file.read_text(encoding="utf-8").split())
        todo = todo[todo.id.isin(wanted)]
    if args.travel_only:
        relevant = todo.category_name.fillna("").str.contains(r"^음식점(?: >|$)|기념품|소품|공예|디자인문구", regex=True)
        unknown = todo.status.ne("ok")
        nontravel_name = todo.name.str.contains(r"병원|의원|약국|학원|교습소|개인택시|치과|한의원|정비|미용|부동산|세무|공인중개", regex=True, na=False)
        todo = todo[relevant | (unknown & ~nontravel_name)]
    todo["priority"] = todo.status.map({"ok": 0, "error": 1, "no_match": 2}).fillna(3)
    todo = todo.sort_values("priority", kind="stable")
    OUT.mkdir(exist_ok=True)
    path = OUT / "results.csv"
    if path.exists() and not args.retry:
        prior = pd.read_csv(path).drop_duplicates("id", keep="last")
        todo = todo[~todo.id.isin(prior.loc[prior.status.ne("error"), "id"])]
    if args.limit:
        todo = todo.head(args.limit)
    print(f"queued={len(todo)} output={path}", flush=True)
    with path.open("a", newline="", encoding="utf-8") as file, ThreadPoolExecutor(max_workers=args.workers) as pool:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if file.tell() == 0:
            writer.writeheader()
        counts = {}
        # Bounded batches avoid scheduling the entire dataset after quota exhaustion.
        records = list(todo.itertuples(index=False))
        for offset in range(0, len(records), args.workers * 2):
            if STOP.is_set():
                break
            for result in pool.map(lambda m: fetch(m, headers), records[offset:offset + args.workers * 2]):
                if result:
                    writer.writerow(result)
                    counts[result["status"]] = counts.get(result["status"], 0) + 1
            file.flush()
            print(f"processed={sum(counts.values())} counts={counts}", flush=True)
    print(f"finished stopped_by_api={STOP.is_set()} counts={counts}", flush=True)
    if STOP.is_set():
        raise SystemExit(2)


if __name__ == "__main__":
    main()
