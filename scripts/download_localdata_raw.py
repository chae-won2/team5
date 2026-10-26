"""
지방행정 인허가데이터(LOCALDATA) 원본 CSV 다운로드 — 부산 원도심 4개 구
- 인증키 필요 없음, API 호출 한도 없음
- 받은 파일은 가공하지 않고 그대로 저장 (팀 업로드 규칙: 원본)
- 저장 위치: data/raw/bin/license_status/YYYYMMDD_인허가_업종_구.csv
- 레포 루트(team5)에서 실행: python scripts/download_localdata_raw.py

사용법
  pip install requests
  python scripts/download_localdata_raw.py

업종 slug 확인법: sample.localdata.go.kr 왼쪽 메뉴에서 업종을 누르면
주소창이 .../public/<slug>/info 로 바뀝니다. 그 <slug> 를 아래 UPJONG에 적으세요.
"""

import os
import time
from datetime import date

import requests

# 업종 이름 -> slug  (일반음식점은 샘플 페이지 주소에서 확인됨)
UPJONG = {
    "일반음식점": "general_restaurants",
    # "휴게음식점": "여기에_slug",   # 샘플 페이지에서 확인 후 입력
    # "제과점영업": "여기에_slug",
}

# 부산 원도심 4개 구 (동구 3270000은 샘플 페이지에서 확인, 나머지는 코드표로 대조)
GUGUN = {"중구": "3250000", "서구": "3260000", "동구": "3270000", "영도구": "3280000"}

OUT_DIR = os.path.join("data", "raw", "bin", "license_status")  # 레포 루트(team5)에서 실행
URL = "https://file.localdata.go.kr/file/download/{slug}/info?orgCode={code}"
HEADERS = {"Referer": "https://file.localdata.go.kr/", "User-Agent": "Mozilla/5.0"}


def main():
    today = date.today().strftime("%Y%m%d")
    os.makedirs(OUT_DIR, exist_ok=True)

    for upjong, slug in UPJONG.items():
        for gu, code in GUGUN.items():
            url = URL.format(slug=slug, code=code)
            res = requests.get(url, headers=HEADERS, timeout=60)
            ctype = res.headers.get("Content-Type", "")
            if res.status_code != 200 or "html" in ctype.lower():
                print(f"[실패] {upjong} {gu}: HTTP {res.status_code}, {ctype} → 브라우저로 직접 받아보세요: {url}")
                continue
            path = os.path.join(OUT_DIR, f"{today}_인허가_{upjong}_{gu}.csv")
            with open(path, "wb") as f:   # 바이트 그대로 저장 (인코딩: CP949일 가능성 큼)
                f.write(res.content)
            print(f"[저장] {path} ({len(res.content) / 1024:.0f} KB)")
            time.sleep(1)


if __name__ == "__main__":
    main()