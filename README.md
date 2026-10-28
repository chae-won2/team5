# 부산 풀코스 · Busan Full Course

부산 원도심의 관광명소와 동백전 가맹점을 연결하는 도보 여행 서비스입니다. 사용자가 카테고리별 후보에서 장소를 하나씩 선택해 방문 순서를 정하고, 완성한 코스를 이메일로 받을 수 있습니다.

서비스: https://busan-full-course.onrender.com/

문서 기준: 2026-10-26 현재 구현

## 사용자 흐름

1. 출발지, 여행시간(30분~6시간), 출발지 복귀 여부를 입력합니다. 출발 날짜(기본값 오늘)·시각(선택, 비우면 코스 완성 시각)도 고를 수 있습니다.
2. 식당·카페/디저트·관광명소·쇼핑을 복수 선택합니다. 미선택 시 모든 카테고리를 볼 수 있습니다.
3. 다음 카테고리의 추천 후보 최대 3곳 중 방문지를 선택합니다. 선택한 출발 날짜·시각 기준으로 휴무/영업종료가 확인된 곳은 후보에 아예 나오지 않고, 영업중으로 확인된 곳은 `영업중` 태그가 붙습니다(조사된 장소만, 전체 840곳 중 229곳). 조사 자료가 없는 곳은 태그 없이 그대로 나옵니다.
4. 선택한 장소를 고정하고 다음 방문지를 추가하거나 제거합니다. 각 장소 옆에 도보·체류 시간대(예: `10:00 ~ 10:05`, `10:05 ~ 11:05`)가 표시됩니다.
5. 코스를 확정하고 이메일 이용 동의를 거쳐 선택한 언어로 전송합니다. 메일에도 같은 시간대가 포함됩니다.

시작 안내 → 조건 입력 → 장소 선택 → 코스 완성의 단계 표시와 블루 테마를 제공합니다. 상단 공식 제휴·부산페이 표시는 유지합니다. 이메일은 같은 색상의 카드형 HTML과 일반 텍스트를 함께 발송하며, 장소별 지도 링크·시간대·확인된 가격·결제 안내를 표시합니다. 금액 합계는 확인된 식당·카페 가격만 합산하며, 방문 날짜도 코스 재열기 링크에 유지합니다.

한국어·영어·일본어·중국어 번체를 지원합니다. 한국어가 아닌 언어에서 관광명소(약 15곳, `official_place_labels.json`)는 한국어 이름 아래에 공식 확인된 외국어 이름을 함께 보여줍니다. 공식 외국어명이 없는 상호는 한국어 이름 아래에 자동 로마자 음역을 보조로 표시합니다. 영어·일본어·번체 화면에서 동일한 로마자 읽기 보조를 사용하며, 공식 번역으로 취급하지 않습니다. 이메일도 같은 기준을 적용합니다.

## 추천 방식

- 첫 장소는 출발지에서, 이후 장소는 직전 선택 장소에서 TMAP 예상 도보 20분 이내여야 합니다.
- 총 시간에 이동·기본 체류·선택한 복귀 구간을 포함합니다. 여행시간 입력은 최대 360분이며, 사용자 코스는 설정값보다 최대 10분 초과까지 경고와 함께 선택·확정할 수 있습니다.
- 시간 내 후보를 먼저 제시하고 부족한 자리는 +10분 이내 초과 후보로 채웁니다.
- 이동시간이 비슷한 후보 사이에서 최근 7일의 1위 노출이 적은 곳을 우선 배치합니다.
- 평점·리뷰 가중치와 강화학습은 운영 추천에 사용하지 않습니다.
- 영업시간은 선택한 출발 날짜·시각 한 시점 기준으로 확인합니다. 휴무/영업종료가 **확인된** 곳만 신규 후보에서 제외하고, 조사 자료가 없는 곳은 제외하지 않고 태그 없이 그대로 보여줍니다. 이미 코스에 넣은 장소는 나중에 휴무로 확인돼도 자동으로 빠지지 않습니다.

목표는 추천 기회 분산입니다. 실제 방문·매출 증가나 사용자 만족을 입증한 결과는 아닙니다. 전역 최적 코스나 전체 장소 전수탐색을 보장하지 않습니다.

## 로컬 실행

프로젝트 루트의 `.env`에 서버 환경변수를 설정합니다. 실제 키·DB 비밀번호는 Git이나 `VITE_` 변수에 넣지 않습니다.

| 환경변수 | 용도 |
|---|---|
| `KAKAO_REST_API_KEY` | 출발 장소 검색 |
| `TMAP_APP_KEY` | 도보 경로·시간 |
| `EXPOSURE_DATABASE_URL` | 서버 전용 PostgreSQL 연결. 로컬 미설정 시 SQLite |
| `BREVO_API_KEY`, `EMAIL_FROM` | Brevo HTTPS 메일 발송 |
| `EMAIL_DELIVERY_ENABLED` | `false`이면 메일 차단 |
| `PUBLIC_SITE_URL` | 메일 코스 재열기 주소. 기본값은 공개 사이트 |

별도 터미널 두 개에서 실행합니다.

```powershell
# 터미널 1 · 프로젝트 루트
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000

# 터미널 2 · 프로젝트 루트
cd frontend
npm ci
npm run dev
```

화면: http://127.0.0.1:5173/ · API 문서: http://127.0.0.1:8000/docs

Vite의 `/api` 프록시는 8000번입니다. 포트 변경 시 `frontend/vite.config.js`도 맞춰야 합니다.

## 데이터와 영속 저장

- 추천 입력: `data/processed/fin/places.csv` → `load_places()`.
- 요일별 영업시간: `data/processed/fin/place_opening_hours.csv` → `load_opening_hours()`. 840곳 중 229곳의 주간 시간표를 보유하며, 계절별·예외시간 등은 자유서술 정보를 별도 보관합니다.
- 출처·체류시간 기준·업종 검토: `data/processed/bin/place_support/`.
- 예상지출 조사·정제: `data/processed/estimated_spend/`, `data/raw/estimated_spend/` (상세는 해당 폴더 README).
- 원본·GIS·과거 매칭·가중치 실험·쇼핑 검수는 `data/raw/bin/`, `data/processed/bin/`, `data/bin/`에 모아 서비스 입력과 분리합니다 (`data/` 바로 아래는 `raw/`, `processed/`, `bin/`만 있음).
- 추천 요청·후보·순위·표시 기록: Supabase 비공개 `app_private.exposure_lists`와 `app_private.exposure_candidates`. Render 재배포와 별개로 유지합니다.
- 완성 코스·사용자 프로필을 저장하는 DB 테이블은 없습니다. 노출 테이블에 이메일·출발 좌표·사용자 ID를 저장하지 않습니다.

시장 자체는 관광명소이고 시장 안 가게는 원래 업종을 유지합니다. 관광명소 전체가 동백전 가맹점은 아니며 명부 등재가 당일 영업·결제 가능 여부를 보증하지 않습니다.

## 검증

```powershell
cd backend
python -m unittest discover -p "test_*.py"

# 프로젝트 루트의 다른 터미널
cd frontend
node --test test_locale.mjs test_schedule.mjs test_category_picker.mjs
npm run build
npm run lint
```

테스트 클라이언트에는 `httpx`가 필요합니다. 외부 발송·경로 요청은 모의 응답으로 검증합니다. 기존 React effect 관련 lint 경고가 남아 있을 수 있습니다.

## 문서와 주요 코드

| 문서 | 내용 |
|---|---|
| [추천 알고리즘](docs/ROUTE_ALGORITHM.md) | 순차 선택·후보·시간 경고 |
| [상위 노출 순환](docs/recommendation_rotation.md) | 순위·집계·영속 저장 |
| [장소 스키마](docs/PLACES_SCHEMA.md) | CSV 계약·기본 체류시간 |
| [카테고리](docs/PLACE_CATEGORIES.md) | 업종·시장·결제 태그 |
| [데이터 관리](docs/DATA_GUIDE.md) | 원본·전처리·GIS·실험 |
| [배포와 DB](docs/DEPLOYMENT.md) | Render·Supabase·환경변수·문제 해결 |

```text
backend/app/services/route.py        후보·이동·체류 계산
backend/app/services/opening_hours.py 요일별 영업시간 판정
backend/app/services/exposure.py     상위 노출 순환·DB 저장
backend/app/services/walking.py      TMAP 보행자 경로
backend/app/routers/recommend.py     순차 추천·재계산·노출 확인 API
backend/app/routers/notify.py        다국어 메일·코스/지도 링크
frontend/src/App.jsx                 순차 선택 상태
frontend/src/schedule.js             출발 날짜·시각·도보/체류 시간대 계산
frontend/src/components/NextPlacePicker.jsx  후보 카드·노출 확인
supabase/exposure.sql               비공개 노출 테이블
Dockerfile / render.yaml            공개 배포
```

미구현: 장소별 체류시간 직접 수정 UI, 장소별 실제 방문 예정 시각까지 반영한 영업시간 판정(현재는 코스 전체에 출발 한 시점만 적용), 노출 대시보드, 방문·결제 추적, 동백전 가맹점 상호명의 공식 외국어 번역 확보(자동 로마자 음역은 구현됨). 예상 소비금액 필드는 있으나 현재 미확보 값을 가상 금액으로 채우지 않습니다.


### 원도심 쇼핑·관광명소 확장

2026-10-26 조사 자료를 합쳐 서비스 장소 840곳을 제공한다. 쇼핑·관광명소는 중구·동구·서구·영도구로 확장했고, 식당·카페는 기존 조사 범위를 유지한다. 관광지 입장료는 식당·카페 예상지출과 별도로 관리한다. 병합 재실행: `python scripts/merge_oldtown_places.py`. 보류 내역과 위치·운영정보 근거는 [통합 명세](docs/PLACES_SCHEMA.md#원도심-조사-데이터-통합-2026-10-26)를 참고한다.
