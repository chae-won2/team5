# 부산 원도심 쇼핑·관광명소 조사 원본 (2026-10-26)

범위: 중구·동구·서구·영도구. 보유 TourAPI 목록, 2026-10-26 상세 API 수집, 기존 검수 장소와 공식 웹 조사를 합친 조사 목록이다. 원도심의 모든 장소를 망라한 전수조사나 서비스 투입 확정 목록이 아니다. 이 폴더는 조사 원본이다. 서비스 통합은 별도 `scripts/merge_oldtown_places.py`와 `data/processed/bin/place_support/oldtown_merge_review.csv`로 추적한다.

## 파일

- oldtown_shopping_attractions.csv: 장소별 조사표(UTF-8 BOM; Excel에서 열 수 있음).
- tourapi_snapshot.json: 원천 목록·키워드 조회·상세 API 응답 및 키를 제외한 요청 조건. 기존 원본에만 있는 장소도 상세 조회 후 유지했다. 목록 미포함은 폐업 의미가 아니다.
- web_evidence.json: 보완한 필드별 웹 출처·확인일·근거 요약.

## 판정 기준

- 동백전은 가능 / 불가 / 확인필요. 가능은 해당 사업자와 주소를 보유 가맹점 명부(2026-04-24)에서 확인한 뜻이며 2026-10-26 현장 결제 성공 확인을 뜻하지 않는다. 명부 미등재만으로 불가 처리하지 않았다.
- 불가는 동백전 공식 FAQ의 제한업종과 운영사 시설 유형을 함께 확인한 대규모점포 공통 결제에 한한다. 독립 임대매장에는 일괄 적용하지 않는다.
- 시장·거리·상가 전체는 개별 점포 확인필요. 무료 입장은 동백전 가능으로 판정하지 않는다. 무료시설 부대매장도 별도 확인한다.
- 일반 신용카드 가능, 온누리상품권 가능, 동백전 앱의 할인카드 발급은 동백전 충전금 결제 근거로 쓰지 않았다.
- 운영시간은 출처 원문 의미를 유지한다. 상시개방을 무조건 24시간으로 바꾸지 않았고 전시실·프로그램·야외 공간 시간을 구분할 필요가 있다. 점포별 상이/기존값/충돌/확인필요 상태는 서비스 자동 영업시간 필터에 바로 사용하지 않는다.
- hours_source_date는 수집·검수 시점이다. 실제 원문 수정일은 inventory_modified_at·원문을 따로 참조한다. 공식검색안내는 검색 결과에서 확인한 공식 문구이며 본문 접속 불안정 등 제한이 있다.
- 입장료는 관광명소만 조사. 쇼핑 상품 가격은 조사하지 않았다. 숫자 빈칸은 미확보이며 무료는 명시 근거가 있을 때만 0으로 기록했다. 프로그램별/조건부 요금은 fee_details·fee_basis를 함께 읽는다.
- 아르떼뮤지엄 할인가는 현재 공식 페이지의 표시값으로서 기간 확인필요. 송도용궁구름다리 일반료는 이전 감사자료 근거라 현장 재확인이 필요하다. 부산타워 어린이 요금은 공식 출처끼리 상이해 숫자로 확정하지 않았다.
- 국제시장 휴무 등 출처 충돌은 review_notes에 남겼다. 종료된 한정행사 운영시간을 평상시 시간으로 쓰지 않았다.
- 신규 웹 조사 장소의 미확보 좌표·행정동은 추측하지 않았다. district는 구 단위이며 admin_dong 판정이 아니다. raw_id는 이 조사 내 안정적인 식별자이며 existing_place_id·tourapi_contentid로 기존 데이터와 연결한다.

## 주요 컬럼

name/district/category/place_type/address/lon/lat: 식별 및 위치. category는 조사상 쇼핑·관광명소 구분이며 TourAPI 쇼핑에 속한 시장도 포함한다. 서비스 통합 단계에서는 기존 PRD의 시장=관광명소 기준으로 재분류할 수 있다.
opening_hours/closed_days/hours_status/hours_source/hours_source_date: 운영 안내와 판정 근거.
entry_fee_status/adult_fee_krw/adult_weekend_fee_krw/child_fee_krw/fee_basis/fee_details/fee_source: 관광지 입장·관람·이용 요금과 적용 조건(원, 1인 기준; 프로그램별 예외 확인).
dongbaek_status/dongbaek_scope/dongbaek_basis/merchant_id/merchant_name/merchant_address/merchant_data_date/dongbaek_source: 결제 여부·범위·명부 연결 근거.
seed_source/inventory_modified_at/checked_at/review_notes: 출발 자료·원천 수정시점·이번 확인일·주의 및 추가 검수 사항.
