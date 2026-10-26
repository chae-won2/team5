# 통합 Place 데이터 계약

기준: 2026-10-26. 추천 API는 `load_places()`로 `data/processed/fin/places.csv`를 읽습니다. 기준표·검수·출처는 `data/processed/bin/place_support/`에 분리합니다. `data/process`는 사용하지 않습니다.

## 컬럼

| 컬럼 | 계약 |
|---|---|
| `id` | 고유 문자열. 가맹점 ID 유지, 관광명소는 `spot:` 접두사 |
| `name`, `address` | 확인된 장소명·주소, 필수 |
| `category` | 식당 / 카페·디저트 / 관광명소 / 쇼핑, 필수 |
| `visit_type` | 기본 체류시간 분류, 필수 |
| `lon`, `lat` | WGS84 경도·위도, 필수 |
| `admin_dong` | 남포동 / 광복동 / 부평동 / 대청동, 필수 |
| `duration_min` | 양의 정수 기본 체류시간, 필수 |
| `estimated_spend` | 대표 메뉴 기준 1인 예상 원화 금액. 미확보는 빈칸. 조사 과정은 `data/processed/estimated_spend/README.md` 참고 (783곳 중 438곳 반영, `scripts/merge_estimated_spend.py`로 재통합) |
| `opening_hours` | 기존 자유서술 영업시간 원문. 요일별 구조화 값과 구분해 보존 |
| `data_date`, `source` | 자료 기준일·출처 |
| `place_type` | merchant / attraction / market |
| `payment_status` | merchant_listed / not_verified |

빈칸은 결측값이며 미확보 금액을 0으로 채우지 않습니다. 로더는 필수값·ID 중복·업종/유형 조합·행정동·좌표 범위·숫자를 검사하고 선택 필드 결측을 `null`로 응답합니다. `rating`·`review_count`·`image_url`은 서비스 명세와 생성 결과에서 제거했습니다. 원천·실험 데이터에는 이 변경을 적용하지 않습니다.

## 요일별 영업시간

`data/processed/fin/place_opening_hours.csv`를 `places.csv.id = place_id`로 연결합니다. 장소 1개에 여러 요일·영업 구간을 기록하는 1:N 구조입니다. Supabase는 현재 노출 이력 전용이며 장소·영업시간 테이블을 생성하거나 이전한 것은 아닙니다.

2026-10-26 기준 1557행, 783곳 중 약 240곳을 수작업으로 조사해 채웠습니다(식당 125곳 + 카페·디저트 중심 115곳). 나머지는 기록이 없어 전부 `unknown`으로 응답합니다. 원본 조사 CSV 2개(식당125·시연용10곳)는 조사자 개인 PC에만 있고 저장소에는 없습니다 — `data/raw/`의 다른 원천과 달리 이 파일은 **재생성 스크립트가 없습니다.** 추가 조사분을 반영하려면 같은 열(상호명·영업여부·월~일·출처·확인일) 형식의 CSV를 받아 장소명으로 `places.csv`와 매칭한 뒤 이 파일에 이어 붙여야 합니다.

| 컬럼 | 계약 |
|---|---|
| `place_id` | `places.csv`에 존재하는 장소 ID, 필수 |
| `weekday` | 월요일 0 ~ 일요일 6. 영업을 시작하는 날짜의 요일, 필수 |
| `status` | `open` / `closed` / `unknown`, 필수. 정규 시간표 기준이며 실시간 영업 확인을 뜻하지 않음 |
| `opens_at`, `closes_at` | `HH:MM`, `open`일 때 필수. 다른 상태는 빈칸 |
| `closes_next_day` | 0 / 1. 익일 종료면 1. `open`일 때 필수, 다른 상태는 빈칸 |
| `source` | 확인 출처 URL 또는 자료명. `open`·`closed` 기록에 필수 |
| `checked_date` | 확인일 `YYYY-MM-DD`. `open`·`closed` 기록에 필수 |

- 기록이 없는 요일은 **미확인**입니다. 휴무나 24시간 영업으로 추정하지 않습니다.
- 브레이크타임은 영업 구간을 나눠 여러 행으로 입력합니다. 예: 월요일 `11:00~15:00`, `17:00~22:00` 두 행.
- 자정 이후 영업은 예를 들어 월요일 `18:00~02:00`, `closes_next_day=1`로 기록합니다.
- 24시간 영업은 `00:00~00:00`, `closes_next_day=1`로 기록합니다.
- 같은 장소·요일의 구간은 중복·겹침 없이 관리하며, `closed`·`unknown`과 `open`을 함께 입력하지 않습니다. 전날부터 이어지는 영업 구간도 확인해야 합니다.
- 공휴일·임시휴무·특정 날짜 예외는 이 주간 시간표만으로 확정하지 않습니다. 추후 별도 예외 구조가 필요합니다.
- 빌더는 이 파일이 없을 때만 헤더를 만들고, 이미 입력된 시간표를 덮어쓰지 않습니다.
- `POST /api/recommend/next`가 `load_opening_hours()`로 이 파일을 읽어 응답의 각 장소에 `opening_status`(`open`/`closed`/`unknown`)를 붙입니다(`backend/app/services/opening_hours.py`). 요청의 `departure_date`(`YYYY-MM-DD`)·`departure_time`(`HH:MM`)을 생략하면 한국시간 현재 날짜·시각을 씁니다.
- 판정은 **전체 코스에 대해 출발 날짜·시각 한 시점만** 확인합니다. 장소별로 실제 도착 예정 시각(화면에 표시되는 `10:05~11:05` 같은 구간)까지 반영하지는 않습니다 — 여러 곳을 들르는 긴 코스에서는 뒤쪽 장소의 실제 영업 여부와 다를 수 있습니다.
- `closed`로 확인된 장소는 `recommend_route`·`next_places`의 신규 후보·대체 목록에서 제외합니다(`route.py`의 `_is_closed()`). `unknown`은 절대 제외하지 않고, 화면에 태그(`영업중`/`영업시간 아님`)만 붙입니다 — 조사되지 않은 소규모 가맹점을 일괄 배제하지 않기 위해서입니다. 이미 사용자가 선택해 코스에 넣은 장소는 이후에 `closed`로 바뀌어도 자동으로 빼지 않습니다(재계산·대체 제안 단계에서만 적용).

## 공식 외국어 표기

`backend/app/services/official_place_labels.json`에 **관광공사·구청 등 공식 출처로 확인된** 영어·일본어·중국어 번체 이름·주소만 수동으로 등록합니다(2026-10-26 기준 관광명소 약 15곳 — 용두산공원, 자갈치시장 등 `spot:curated:` 장소). 기계번역은 쓰지 않습니다. 확인 안 된 상호·주소는 한국어로 유지합니다(`official_fallback`) — 번역을 추측해서 보여주면 실제 간판·지도 표기와 달라져 오히려 혼란을 줄 수 있기 때문입니다.

- `POST /api/recommend/next`의 `language`(`ko`/`en`/`ja`/`zh-TW`, 기본 `ko`)로 요청하면 응답의 각 장소에 `official_name`을 붙입니다(`backend/app/services/place_labels.py`의 `official_labels()`, `route.py`에서 호출). `language=ko`이거나 일치하는 등록 정보가 없으면 빈 문자열입니다 — `name`(한국어 원본)은 항상 그대로 둡니다.
- 식당·카페 등 동백전 가맹점 766곳은 이 파일에 없어서 `official_name`이 항상 빈 문자열입니다. 상호명 번역/음역은 아직 별도로 구현하지 않았습니다.
- 이메일(`notify.py`)도 같은 함수를 쓰지만 우선순위가 반대입니다 — 메일은 공식 외국어명을 본문에 먼저 쓰고 한국어 원본을 보조로 붙이고, 화면은 한국어 이름을 그대로 두고 공식 외국어명을 그 아래 보조 줄로 보여줍니다.

## 기본 체류시간

| visit_type | 분 |
|---|---:|
| general_restaurant | 60 |
| quick_meal | 30 |
| seated_cafe | 45 |
| takeaway_dessert | 15 |
| general_shopping | 40 |
| souvenir_shop | 20 |
| retail_store | 25 |
| scenic_spot | 30 |
| exhibition_experience | 60 |
| traditional_market | 60 |

출처는 `duration_rules.csv`입니다. 사용자 제공 기준·담당자 자료의 초기 가정이며 실측 평균이 아닙니다. 장소별 체류시간 수정 UI·일정별 override 저장은 아직 구현하지 않았습니다.

## 재생성

현재 `build_catalog()` 함수는 없습니다. `scripts/build_places.py`가 기존 분류 함수와 승인된 GIS MVP 매칭 결과를 재사용합니다. 공간 검사는 전처리 단계에서 QGIS Python으로 수행하고 서비스 서버에는 QGIS가 필요하지 않습니다.

프로젝트 루트에서 아래처럼 쇼핑·관광명소 입력을 모두 지정합니다. 생략하면 부분 결과로 덮어쓸 수 있으므로 재생성 전에 산출물을 보관하세요.

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
& "C:/Program Files/QGIS 3.16/bin/python-qgis-ltr.bat" "$PWD/scripts/build_places.py" --shopping-file "$PWD/data/bin/shopping_verification/shopping_places_final.csv" --tourism-file "$PWD/data/processed/bin/mvp_tourist_spots.csv"
```

쇼핑 선정 ID는 좌표·정규화 상호로 기존 가맹점에 연결하며 최종 출력은 가맹점 ID를 사용합니다. 관광명소는 유형·좌표가 필요하고 행정동은 경계로 판정합니다. 산출물은 서비스 CSV, 출처 CSV, 검수 CSV, `summary.json`입니다. JSON의 과거 호환 필드 `backend_switched`를 현재 배포 상태로 해석하지 마세요.

## 일정·노출 데이터와의 관계

선택 순서는 프런트 상태와 API의 `stop_ids`에서 관리하며 완성 일정 테이블은 없습니다. 도보·체류·선택한 복귀시간을 합산하고 설정 시간보다 최대 10분 초과까지 경고 후 허용하며, 그보다 초과하면 후보에서 제외합니다. 영속 DB에는 추천 요청·정책·여행 조건·적격 후보별 도보/예상 시간·공통 기대 노출·배정 순위·목록 표시 확인 시각을 저장합니다. 운영과 실험 기록은 구분합니다. 분류 검토 CSV는 고객 리뷰나 방문 기록이 아닙니다.

화면의 출발 날짜·시각은 백엔드에 저장하지 않고 요청마다 전달합니다(위 `opening_status` 판정에만 씁니다). 각 장소 옆 도보·체류 시간대(`10:00~10:05`, `10:05~11:05`)는 프런트가 `frontend/src/schedule.js`의 `buildSchedule()`로 선택 순서·도보/체류 분을 누적해 클라이언트에서 계산하며, 자정을 넘기면 "익일 HH:MM"으로 표시합니다. 이 계산은 날짜를 쓰지 않고 시각만 사용합니다 — `opening_status`처럼 요일이 필요한 판정과는 별개 로직입니다.
