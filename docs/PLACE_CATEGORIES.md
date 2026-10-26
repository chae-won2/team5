# 서비스 카테고리와 장소 구분

기준: 2026-10-23. 운영 입력은 `data/processed/fin/places.csv`입니다. `recommendation_places.csv`와 `shopping_mvp_candidates.csv`는 이전 파이프라인 자료입니다.

| 카테고리 | 내용 |
|---|---|
| 식당 | 일반 식당·간편 식사 |
| 카페/디저트 | 카페·빵·떡·빙수·포장 디저트 등 |
| 관광명소 | 관광지·전시/문화시설·시장 자체 |
| 쇼핑 | 담당자 선정 가맹점 목록 |

CSV에서는 `카페·디저트`, 화면·API에서는 `카페/디저트`를 사용하며 같은 카테고리로 처리합니다. 복수 선택이 가능하고 별도 전체 버튼은 없습니다. 미선택 시 다음 방문지 화면에서 모든 카테고리를 제시합니다.

## 시장과 가게

시장 자체는 관광명소인 독립 방문지(`place_type=market`)입니다. 시장 안 카페·식당은 개별 가게(`merchant`)이며 본래 업종을 유지합니다. 시장 소속 근거는 `data/processed/bin/place_support/place_sources.csv`·GIS에 별도 보관합니다. 상권영역 포함은 법적 소속·층별 위치·현재 영업을 보증하지 않습니다.

## 결제·선정 태그

- `merchant_listed`: 동백전 명부 등재. 화면의 `#동백전결제가능`은 명부 근거이며 실제 결제 가능 여부는 방문 전 확인 대상입니다.
- `not_verified`: 관광명소 자체의 결제 여부 미확인. 모든 관광명소가 가맹점은 아닙니다.
- `#부산의맛`: `data/raw/dongbaekjeon/2026_부산의맛_식당목록.csv`와 검증 규칙으로 연결한 장소에만 표시합니다. 점수 가산이 아닙니다.

`scripts/build_places.py`가 승인된 MVP 분류와 관광·쇼핑 선정을 통합합니다. 쇼핑 입력은 `data/shopping_verification/shopping_places_final.csv`, 관광명소 입력은 `data/processed/bin/mvp_tourist_spots.csv`입니다. 필수값 부족·좌표/유형 불명확·권역 밖·원천 충돌은 검수 대상으로 분리합니다. 업종 검수 파일은 고객 리뷰가 아니며 운영 후보를 Google 리뷰 유무로 교체하지 않습니다.
