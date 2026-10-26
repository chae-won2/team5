"""Build the four-category MVP catalog from reviewed offline classifications.
Original merchants and classification files are never overwritten.
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed'
DATA_BIN = DATA / 'bin'
DISTRICTS = r'부산(?:광역시)?\s+(?:중구|서구|동구|영도구)\s'
COLUMNS = ['id', 'name', 'address', 'lat', 'lon', 'category', 'place_type',
           'payment_status', 'source', 'data_date', 'category_evidence']


def category_for(row):
    tags = set(row.purpose_tags.split('|'))
    if '소품·기념품 쇼핑' in tags:
        return '쇼핑'
    if '커피·디저트' in tags:
        return '카페·디저트'
    if '식사' in tags:
        return '식당'
    if '간식·먹거리' in tags:
        # Dessert retailers belong with cafes; savory snacks remain restaurants.
        evidence = json.loads(row.evidence)
        dessert = any(detail in {'빵/도넛', '떡/한과', '아이스크림/빙수'} or
                      any(word in detail for word in ('제과', '베이커리', '도넛', '아이스크림', '빙수', '디저트', '떡,한과'))
                      for _, _, detail in evidence)
        return '카페·디저트' if dessert else '식당'
    return None


def build():
    tags = pd.read_csv(DATA_BIN / 'travel_purposes/merchants_travel_purposes.csv').fillna('')
    delta = DATA_BIN / 'travel_purposes/kakao_update_20261021/merchants_travel_purposes_delta.csv'
    if delta.exists():
        tags = pd.concat([tags, pd.read_csv(delta).fillna('')]).drop_duplicates('id', keep='last')
    merchants = pd.read_csv(DATA / 'merchants.csv').fillna('')
    tags = tags[tags.classification_status.eq('classified') & tags.address.str.contains(DISTRICTS, regex=True)].copy()
    tags['category'] = [category_for(row) for row in tags.itertuples()]
    tags = tags.dropna(subset=['category'])
    tags = tags.drop(columns=['source', 'data_date'], errors='ignore').merge(
        merchants[['id', 'source', 'data_date']], on='id', validate='one_to_one')
    tags['place_type'] = 'merchant'
    tags['payment_status'] = 'merchant_listed'
    tags['category_evidence'] = tags.evidence
    # Stronger dual-source gift classifications first. Selection is explicit and reviewable.
    shopping = tags[tags.category.eq('쇼핑')].copy()
    shopping['dual_source'] = shopping.evidence.map(lambda value: '기념품판매' in value or '소품샵' in value)
    shopping = shopping.sort_values(['dual_source', 'id'], ascending=[False, True]).head(10)
    shopping['selection_note'] = 'MVP 임시 후보: 원도심 가맹점·기념품 업종 근거, 영업/판매품목 현장 검수 전'
    shopping[COLUMNS + ['selection_note']].to_csv(DATA_BIN / 'shopping_mvp_candidates.csv', index=False, encoding='utf-8-sig')
    tags = pd.concat([tags[tags.category.ne('쇼핑')], shopping], ignore_index=True)

    spots = pd.read_csv(DATA_BIN / 'tourist_spots.csv').fillna('')
    spots = spots[spots.category_major.isin(['관광지', '문화시설', '전통시장']) &
                  spots.address.str.contains(DISTRICTS, regex=True)].copy()
    # Use the market record when TourAPI also lists the same named market.
    spots = spots.sort_values('category_major', key=lambda s: s.ne('전통시장'))
    spots = spots.drop_duplicates(['name', 'address'])
    spots['category'] = '관광명소'
    spots['place_type'] = spots.category_major.map(lambda value: 'market' if value == '전통시장' else 'attraction')
    spots['payment_status'] = 'not_verified'
    spots['category_evidence'] = spots.category_major + ' / ' + spots.category_minor
    spots['id'] = 'spot:' + spots.id
    catalog = pd.concat([tags[COLUMNS], spots[COLUMNS]], ignore_index=True)
    catalog = catalog.drop_duplicates('id')
    for column in ['lat', 'lon']:
        catalog[column] = pd.to_numeric(catalog[column], errors='coerce')
    catalog = catalog[catalog.lat.between(34.9, 35.4) & catalog.lon.between(128.7, 129.4)]
    catalog.to_csv(DATA_BIN / 'recommendation_places.csv', index=False, encoding='utf-8-sig')
    summary = {'categories': catalog.category.value_counts().to_dict(), 'total': len(catalog),
               'market_destinations': int(catalog.place_type.eq('market').sum()),
               'districts': ['중구', '서구', '동구', '영도구'],
               'limitations': ['분류 근거에 따른 후보이며 정확도 수동 검수 전', '쇼핑 10곳은 임시 후보',
                              '가맹점 명부 등재가 현재 결제 가능 여부를 보증하지 않음',
                              '관광명소·시장 자체는 동백전 결제 확인 대상이 아님',
                              '시장 경계 내 개별 점포 소속 판정은 별도 GIS 작업']}
    (DATA_BIN / 'recommendation_places_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    build()
