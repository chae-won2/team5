# TourAPI 원천 자료 안내

이 폴더는 한국관광공사 TourAPI 관광지 등 원천을 보관합니다. 파일명 `tour_consumption.md`는 과거 이름이며 이 문서는 관광소비 실측 데이터나 노출 통계 안내가 아닙니다.

`scripts/fetch_tourapi.py`는 관광 원천 수집 스크립트입니다. 재실행은 API 권한·쿼터·스크립트 출력 경로를 확인한 뒤 진행하고 기존 원본을 보존합니다. API 키는 프로젝트 루트 `.env`에서 관리하며 원천 파일·문서에 넣지 않습니다.

선정 관광명소의 좌표·MVP 경계 검사는 `scripts/build_mvp_tourism.py`, 서비스 통합은 `scripts/build_places.py`에서 수행합니다. 원천 관광지 전체가 운영 추천에 포함되는 것은 아닙니다. [데이터 관리](../../../docs/DATA_GUIDE.md)와 [장소 계약](../../../docs/PLACES_SCHEMA.md)을 참고하세요.
