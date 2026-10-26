# 데이터 관리와 재생성

기준: 2026-10-26. 현재는 수집만 하는 단계가 아니라 서비스용 장소 통합·GIS 검수·실험·영속 노출 기록을 함께 관리합니다.

## 자료 구분

| 위치 | 역할 |
|---|---|
| `data/processed/merchants.csv`, `data/processed/fin/places.csv` | 서빙 입력. 백엔드가 직접 읽는 파일 (`load_merchants()`, `load_places()`) |
| `data/raw/dongbaekjeon/2026_부산의맛_식당목록.csv` | 서빙 입력. `#부산의맛` 태그 매칭용 원본 |
| `data/processed/fin/place_opening_hours.csv` | 서빙 입력. [요일별 영업시간](PLACES_SCHEMA.md#요일별-영업시간) |
| `data/processed/estimated_spend/`, `data/raw/estimated_spend/` | 예상지출 조사·정제 자료. 상세는 `data/processed/estimated_spend/README.md` |
| `data/raw/bin/` | 동백전·상가·TourAPI·시장·공공 지정 등 원천 보관. 서빙에는 쓰이지 않고 전처리 스크립트 입력으로만 사용 |
| `data/processed/bin/place_support/` | 체류 기준·출처·업종 검수·관광지 좌표 근거 |
| `data/processed/bin/GIS/mvp/` | 행정동 4곳의 가맹점·분류 작업 자료 |
| `data/processed/bin/GIS/boundaries/` | 행정동·시장 상권영역과 출처 |
| `data/processed/bin/GIS/full_busan/` | 전체 조사 스냅샷. 최신 서비스 명부가 아님 |
| `data/processed/bin/travel_purposes/` | 여행 목적 분류·후속 매칭·검토 |
| `data/bin/shopping_verification/` | 담당자 선정 쇼핑 입력 |
| `data/bin/experiments/weights_v01/` | 리뷰 기반 40곳 실험·수동 교체 이력. 운영 미반영 |
| `data/bin/experiments/weights_400/` | 식당·카페 400곳 엑셀 표본. 리뷰 조건 없음 |
| Supabase `app_private.exposure_lists` / `app_private.exposure_candidates` | 추천 요청·조건·후보·배정 순위·표시 이력. 운영/실험 구분 |

`data/raw/bin/`, `data/processed/bin/`, `data/bin/`은 백엔드가 읽지 않는 원천·중간·레거시·실험 산출물을 모아두는 자리다. `data/` 바로 아래에는 `processed/`, `raw/`, `bin/`만 둔다. 전처리 스크립트는 여전히 이 경로를 입력·출력으로 사용하며, 재생성 가능하다는 이유로 git 추적에서 제외하지 않는다.

원본·전체 가맹점·업종 분류 가능 데이터·최종 서비스 장소·Google 연결률은 분모가 다릅니다. 서로 다른 집계의 비율을 섞어 발표하지 않습니다.

## 처리 흐름

동백전 원본(`data/raw/bin/dongbaekjeon/`) → `scripts/geocode_dongbaekjeon.py`로 좌표 부여(`data/processed/bin/`) → `scripts/clean_data.py`로 `merchants.csv` 생성(`data/processed/`) → 카카오/상가 업종 연결·검토 → 행정동·시장 경계 분석 → `scripts/build_places.py`로 승인된 관광·쇼핑과 서비스 CSV 통합(`data/processed/fin/places.csv`).

`scripts/build_mvp_tourism.py`는 선정 관광명소의 좌표 근거·유형을 합쳐 MVP 관광지와 검토 목록을 만듭니다. QGIS 전처리 재생성은 [장소 계약](PLACES_SCHEMA.md)을 따릅니다. 서비스는 원천 API 매칭을 요청마다 반복하지 않습니다.

`recommendation_places.csv` 및 `build_recommendation_places.py`는 이전 통합 파이프라인 자료입니다. `load_to_supabase.py`와 `supabase/schema.sql`은 기존 원천 테이블 적재용이며 현재 노출 DB 초기화와 다릅니다.

## 표본·검수

40곳 실험은 식당 17·카페 17·관광명소 3·쇼핑 3이며 수동 장소 교체를 포함합니다. 전체 Google 확보율을 추정하는 무작위 표본으로 해석하지 않습니다.

400곳은 최종 서비스 명부의 동백전 등재 식당 250·카페 150곳을 업종×행정동별 비복원 추출했습니다. 대청동 보유량 때문에 남포 116·광복 116·부평 115·대청 53으로 배정했습니다. 리뷰·평점·Google 등록·도보시간을 선정 기준으로 쓰지 않았습니다. 동백전 전체 가맹점의 단순무작위 표본은 아닙니다. 엑셀은 별도 산출물이며 저장소에 항상 포함된다고 가정하지 않습니다.

GIS·기존 검수 안내에 적힌 건수와 상태는 해당 작업 시점 기록입니다. 상권 경계 포함은 법적 소속 판정이 아니고 고객 리뷰 수집과 업종 검수도 별개입니다.

예상지출은 `data/raw/estimated_spend/merchant_spend_400_original.csv`(수작업 400곳) → `scripts/clean_estimated_spend.py`(숫자 가격 분리) → 추가 웹 조사 2회 → `scripts/merge_estimated_spend.py`로 `fin/places.csv`에 ID 매칭 반영했습니다. 전 과정과 검증 기록은 `data/processed/estimated_spend/README.md`에 있습니다. 세 스크립트 모두 재실행 시 같은 결과를 내도록 검사합니다.

요일별 영업시간(`place_opening_hours.csv`)은 수작업 조사 CSV 2개(식당125·시연용10곳)를 장소명으로 `places.csv`와 매칭해 만들었습니다. 다른 원천과 달리 **원본 조사 CSV와 재생성 스크립트가 저장소에 없습니다** — 조사자 개인 파일에서 바로 변환했습니다. 추가 반영 시 같은 형식(상호명·영업여부·월~일·출처·확인일)의 CSV와 장소명 매칭이 필요합니다.

## 변경 원칙

- 원본은 보존하고 재생성은 별도 산출물로 검증합니다. 삭제는 담당자 확인 후 진행합니다.
- 이름·업종·좌표·영업·결제 상태를 임의 추측으로 채우지 않습니다. 결측과 실제 0을 구분합니다.
- 날짜는 원천 기준일과 조회일을 구분합니다. 수집일만 알면 그 사실을 명시합니다.
- API 캐시·저장·출처 표시 조건은 공급자별로 확인합니다. Google place ID와 평점·리뷰 내용의 저장 조건은 같지 않습니다.
- `.env`·비밀번호·비밀 API 응답은 데이터 폴더나 문서에 넣지 않습니다.
- 영업시간 일부 확보와 현재 영업 가능 판정은 다릅니다. 현재 추천은 영업시간으로 필수 제외하지 않습니다.
