> 문서 상태 · 2026-10-23 정리: 경계 원천과 공간 판정 방법의 기록입니다. 경계 포함은 법적 소속·현재 영업·결제 가능 여부를 보증하지 않습니다. 현재 서비스 설명은 저장소 README와 docs 문서를 기준으로 합니다.

# 부산 전통시장 상권영역

- 출처: 부산광역시 Big-데이터웨이브 지도 기반 데이터
- 안내: https://data.busan.go.kr/bdip/opendata/mapBasedData.do
- 공개 WFS: https://data.busan.go.kr/geoserver/map/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=map%3ATB_COMMERCIAL_AREA_JEONTONG&outputFormat=application%2Fjson&maxFeatures=1000&srsName=EPSG%3A4326
- 레이어: map:TB_COMMERCIAL_AREA_JEONTONG
- 조회일: 2026-10-21
- 원천 객체 수: 197
- 좌표계: EPSG:4326 (경도, 위도)
- 변환: GeometryCollection에서 Polygon을 추출해 MultiPolygon으로 저장. 경계 좌표 변경 없음.
- 한계: 전통시장 상권영역이며 법적 시장구역 또는 공식 소속 점포명부와 동일하다고 확정할 수 없음. 기준연도는 서비스 메타데이터에서 확인되지 않음.
