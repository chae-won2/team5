"""Build reviewable travel-purpose tags offline; never replace production CSVs."""
import json
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1] / "data/processed"
ROOT_BIN = ROOT / "bin"
OUT = ROOT_BIN / "travel_purposes"


def key(value):
    # Preserve branch names and parentheses content to avoid merging different branches.
    value = re.sub(r"주식회사|유한회사|\(주\)|\(유\)", "", str(value))
    return re.sub(r"[^a-z0-9가-힣]", "", value.lower())


def classify(source, major, detail):
    detail, major = str(detail), str(major)
    if source == "kakao":
        parts = [p.strip() for p in detail.split(">")]
        if len(parts) >= 2 and parts[:2] == ["음식점", "카페"]:
            return "커피·디저트", "classified", "카카오 카페 상세업종"
        if len(parts) >= 2 and parts[:2] == ["음식점", "간식"]:
            return "간식·먹거리", "classified", "카카오 간식 상세업종"
        if len(parts) >= 2 and parts[:2] == ["음식점", "분식"]:
            return "식사|간식·먹거리", "classified", "분식은 두 목적에 해당"
        if len(parts) >= 2 and parts[:2] == ["음식점", "술집"]:
            return "", "outside_scope", "주점은 현재 여행 목적에서 제외"
        if parts[0] == "음식점":
            return ("식사", "classified", "식당 상세업종") if len(parts) > 1 else ("", "review", "음식점 대분류만 있음")
        if any(p in {"기념품", "기념품판매", "소품샵"} for p in parts):
            return "소품·기념품 쇼핑", "classified", "기념품/소품 명시 업종"
        if any(word in detail for word in ["공예", "디자인문구", "문구", "생활용품", "장식", "귀금속"]):
            return "", "review", "판매품목 및 관광 쇼핑 적합성 확인 필요"
        return "", "outside_scope", "현재 네 가지 여행 목적 외 업종"
    if detail == "기념품점":
        return "소품·기념품 쇼핑", "classified", "상가정보 소분류 기념품점"
    if major == "음식":
        if detail == "카페":
            return "커피·디저트", "classified", "상가정보 비알코올 업종"
        if detail in {"빵/도넛", "떡/한과", "아이스크림/빙수"}:
            return "간식·먹거리", "classified", "상가정보 간식 소분류"
        if detail in {"김밥/만두/분식", "토스트/샌드위치/샐러드"}:
            return "식사|간식·먹거리", "classified", "식사/간식 겸용 소분류"
        if detail == "그 외 기타 간이 음식점":
            return "", "review", "간이음식은 식사/간식 세부 구분 필요"
        if "주점" in detail or detail == "생맥주 전문":
            return "", "outside_scope", "주점은 현재 여행 목적에서 제외"
        if detail == "구내식당":
            return "", "review", "일반 관광객 이용 가능 여부 확인 필요"
        return "식사", "classified", "상가정보 음식 업종"
    if major == "소매" and detail in {"그 외 기타 상품 전문 소매업", "주방/가정용품 소매업", "예술품 소매업", "시계/귀금속 소매업", "문구/회화용품 소매업", "액세서리/잡화 소매업", "장난감 소매업"}:
        return "", "review", "소매 업종만으로 소품/기념품 확정 불가"
    return "", "outside_scope", "현재 네 가지 여행 목적 외 업종"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--rematch-file", type=Path)
    parser.add_argument("--delta-only", action="store_true", help="Write updated rows only; preserve the existing full dataset")
    args = parser.parse_args()
    output = args.output_dir
    assert classify("kakao", "", "음식점 > 카페 > 디저트카페")[0] == "커피·디저트"
    assert classify("kakao", "", "서비스,산업 > 공간대여 > 스터디카페,스터디룸")[1] == "outside_scope"
    assert classify("sangga", "소매", "시계/귀금속 소매업")[1] == "review"
    assert classify("sangga", "소매", "기념품점")[0] == "소품·기념품 쇼핑"
    assert classify("sangga", "음식", "빵/도넛")[0] == "간식·먹거리"
    assert key("본죽(서면점)") != key("본죽(해운대점)")
    output.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(ROOT / "merchants.csv").fillna("")
    k = pd.read_csv(ROOT_BIN / "_kakao_category_cache.csv").fillna("").drop_duplicates("id", keep="last")
    rematched = {}
    category_records = k
    if args.rematch_file:
        rematch = pd.read_csv(args.rematch_file).fillna("").drop_duplicates("id", keep="last")
        accepted = rematch[rematch.status.eq("accepted")]
        rematched = accepted.set_index("id").to_dict("index")
        category_records = pd.concat([k, accepted.assign(status="ok")], ignore_index=True).drop_duplicates("id", keep="last")
    raw_path = sorted((ROOT.parent / "raw/bin/sangga").glob("*.csv"))[-1]
    columns = {"상호명": "name", "지점명": "branch", "상권업종대분류명": "category_major",
               "상권업종소분류명": "category_minor", "도로명주소": "address", "경도": "lon", "위도": "lat"}
    s = pd.read_csv(raw_path, usecols=list(columns), encoding="utf-8-sig").rename(columns=columns).fillna("")
    s = s[pd.to_numeric(s.lon, errors="coerce").notna() & pd.to_numeric(s.lat, errors="coerce").notna()].copy()
    inventories = []
    for source, frame, cols in [("kakao", category_records[category_records.status.eq("ok")], ["category_group_name", "category_name"]),
                                ("sangga", s, ["category_major", "category_minor"])]:
        for (major, detail), count in frame.groupby(cols).size().items():
            tags, status, reason = classify(source, major, detail)
            inventories.append(dict(source=source, major=major, detail=detail, source_records=int(count),
                                    purpose_tags=tags, decision=status, reason=reason))
    pd.DataFrame(inventories).to_csv(output / "category_mapping.csv", index=False, encoding="utf-8-sig")
    groups = {}
    for row in s.itertuples(index=False):
        groups.setdefault(key(row.name), []).append(row)
        if row.branch and not key(row.name).endswith(key(row.branch)):
            groups.setdefault(key(row.name + row.branch), []).append(row)
    cached = k.set_index("id").to_dict("index")
    results = []
    for merchant in m.itertuples(index=False):
        evidence = []
        identity_evidence = []
        hit = cached.get(merchant.id)
        new_hit = rematched.get(merchant.id)
        if new_hit:
            evidence.append(("kakao", new_hit["category_group_name"], new_hit["category_name"]))
            identity_evidence.append(dict(source="kakao_rematch", place_id=new_hit["place_id"],
                place_name=new_hit["place_name"], address=new_hit["road_address"],
                distance_m=new_hit["distance_m"], name_similarity=new_hit["name_similarity"],
                address_match=new_hit["address_match"]))
        elif hit and hit["status"] == "ok" and len(key(merchant.name)) >= 2 and key(merchant.name) == key(hit["place_name"]):
            evidence.append(("kakao", hit["category_group_name"], hit["category_name"]))
            identity_evidence.append(dict(source="kakao", place_name=hit["place_name"], verification="normalized_name_only"))
        for candidate in groups.get(key(merchant.name), []):
            meters = np.hypot((candidate.lon-merchant.lon)*91000, (candidate.lat-merchant.lat)*111320)
            if meters <= 100:
                evidence.append(("sangga", candidate.category_major, candidate.category_minor))
                identity_evidence.append(dict(source="sangga", place_name=candidate.name, branch=candidate.branch,
                                              address=candidate.address, distance_m=round(float(meters), 1)))
        evidence = list(dict.fromkeys(evidence))
        decisions = [(e, classify(*e)) for e in evidence]
        tag_sets = {d[0] for _, d in decisions if d[1] == "classified"}
        outside = any(d[1] == "outside_scope" for _, d in decisions)
        conflict = len(tag_sets) > 1 or (bool(tag_sets) and outside)
        if conflict:
            tags, status, reason = "", "review", "동일 상호 후보 또는 데이터 소스 간 분류 충돌"
        elif tag_sets:
            tags, status, reason = next(iter(tag_sets)), "classified", "상호 정규화 일치 기반; 원천 분류 적용"
        elif any(d[1] == "review" for _, d in decisions):
            tags, status, reason = "", "review", "상세 품목/목적 수동 확인 필요"
        elif evidence:
            tags, status, reason = "", "outside_scope", "현재 여행 목적 외 업종"
        else:
            tags, status, reason = "", "unmatched", "동일 가게 연결 근거 부족"
        result = dict(id=merchant.id, name=merchant.name, address=merchant.address, lat=merchant.lat, lon=merchant.lon,
                      source=merchant.source, data_date=merchant.data_date,
                      purpose_tags=tags, classification_status=status, reason=reason,
                      evidence=json.dumps(evidence, ensure_ascii=False),
                      identity_evidence=json.dumps(identity_evidence, ensure_ascii=False), market_membership="unknown")
        results.append(result)
    result = pd.DataFrame(results)
    assert len(result) == len(m) and result.id.is_unique
    assert result[result.classification_status.ne("classified")].purpose_tags.eq("").all()
    export = result[result.id.isin(rematched)] if args.delta_only else result
    filename = "merchants_travel_purposes_delta.csv" if args.delta_only else "merchants_travel_purposes.csv"
    export.to_csv(output / filename, index=False, encoding="utf-8-sig")
    export[export.classification_status.eq("review")].to_csv(output / "review_queue.csv", index=False, encoding="utf-8-sig")
    samples = [g.sample(n=min(25, len(g)), random_state=42) for _, g in export.groupby(["classification_status", "purpose_tags"])]
    (pd.concat(samples) if samples else export).to_csv(output / "validation_sample.csv", index=False, encoding="utf-8-sig")
    summary = dict(total=len(result), statuses=result.classification_status.value_counts().to_dict(),
                   purposes=result.loc[result.purpose_tags.ne(""), "purpose_tags"].str.split("|").explode().value_counts().to_dict(),
                   limitations=["카카오 기존 캐시는 주소/좌표 없어 상호일치만 검증 가능", "상가 원본 소분류 사용; 동일 상호 100m 이내 후보의 충돌은 검토", "시장 소속은 경계/점포목록 없으므로 unknown", "실제 정확도는 수동 표본 검수 전 미확정"])
    summary["exported_rows"] = len(export)
    summary["delta_only"] = args.delta_only
    if args.delta_only:
        summary["application"] = "기존 travel_purposes/merchants_travel_purposes.csv에 이 CSV를 id 기준으로 덮어 합친 결과의 전체 집계. 원본 파일은 변경하지 않음."
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
