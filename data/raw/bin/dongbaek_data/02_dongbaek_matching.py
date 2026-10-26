import pandas as pd
import re
from pathlib import Path

# 프로젝트 폴더 경로
BASE_DIR = Path(__file__).resolve().parent.parent

# 원본 데이터 경로
RAW_DIR = BASE_DIR / "data" / "raw"

# 데이터 불러오기
dongbaek = pd.read_csv(
    RAW_DIR / "부산광역시_지역화폐(동백전) 가맹점 현황_20260424.csv",
    encoding="utf-8-sig"
)

food = pd.read_csv(
    BASE_DIR / "data" / "processed" / "중구_음식 - 중구_음식 (2).csv",
    encoding="utf-8-sig"
)

# 원본 데이터 확인
print("동백전:", dongbaek.shape)
print("상가정보:", food.shape)

print("\n동백전 컬럼:")
print(dongbaek.columns.tolist())

print("\n상가정보 컬럼:")
print(food.columns.tolist())

# 분석 대상 행정동
target_dongs = ['남포동', '광복동']

# 남포동·광복동 음식점 추출
nampo_food = food[
    food['행정동명'].isin(target_dongs)
].copy()

print("남포·광복 음식점:", len(nampo_food))
# 주소의 공백과 부산 표기를 통일
dongbaek['주소_정리'] = (
    dongbaek['주소']
    .fillna('')
    .str.replace('부산광역시', '부산', regex=False)
    .str.replace(r'\s+', ' ', regex=True)
    .str.strip()
)

# 중구 가맹점 추출
junggu_dongbaek = dongbaek[
    dongbaek['주소_정리'].str.startswith('부산 중구 ')
].copy()

print("중구 동백전 가맹점:", len(junggu_dongbaek))
print("\n남포·광복 행정동별 음식점:")
print(nampo_food['행정동명'].value_counts())

print("\n중구 동백전 주소 샘플:")
print(
    junggu_dongbaek[
        ['가맹점 명', '주소_정리']
    ].head(5).to_string(index=False)
)
def clean_name(name):
    if pd.isna(name):
        return ""

    name = str(name).lower()
    name = re.sub(r"[^가-힣a-z0-9]", "", name)

    return name
nampo_food['상호명_정리'] = (
    nampo_food['상호명'].apply(clean_name)
)

junggu_dongbaek['상호명_정리'] = (
    junggu_dongbaek['가맹점 명'].apply(clean_name)
)
print("\n상가정보 상호명 정규화:")
print(
    nampo_food[
        ['상호명', '상호명_정리']
    ].head(10).to_string(index=False)
)

print("\n동백전 상호명 정규화:")
print(
    junggu_dongbaek[
        ['가맹점 명', '상호명_정리']
    ].head(10).to_string(index=False)
)
nampo_food['주소_정리'] = (
    nampo_food['도로명주소']
    .fillna('')
    .str.replace('부산광역시', '부산', regex=False)
    .str.replace(r'\s+', ' ', regex=True)
    .str.strip()
)
exact_matches = nampo_food.merge(
    junggu_dongbaek[
        ['가맹점 명', '주소_정리', '상호명_정리']
    ],
    on=['주소_정리', '상호명_정리'],
    how='inner'
)
print("정확 일치 매칭 행 수:", len(exact_matches))

print(
    "매칭된 고유 음식점 수:",
    exact_matches['상가업소번호'].nunique()
)

print(
    "\n정확 일치 매칭 결과:"
)

print(
    exact_matches[
        ['상호명', '가맹점 명', '주소_정리']
    ].head(15).to_string(index=False)
)
# 정확 일치한 음식점의 고유 ID
matched_ids = exact_matches['상가업소번호'].unique()

# 정확 일치하지 않은 음식점 추출
unmatched_food = nampo_food[
    ~nampo_food['상가업소번호'].isin(matched_ids)
].copy()

print("정확 일치 음식점:", len(matched_ids))
print("추가 확인 대상:", len(unmatched_food))

print(
    unmatched_food[
        ['상호명', '행정동명', '도로명주소', '지번주소']
    ].head(15).to_string(index=False)
)
nampo_food['상가업소번호'].isin(matched_ids)

print("\n[상가정보 - 이재모피자]")
print(
    unmatched_food[
        unmatched_food['상호명'].str.contains('이재모피자', na=False)
    ][['상호명', '도로명주소', '지번주소']].to_string(index=False)
)

print("\n[동백전 - 이재모 관련 가맹점]")
print(
    junggu_dongbaek[
        junggu_dongbaek['가맹점 명'].str.contains('이재모', na=False)
    ][['가맹점 명', '주소_정리']].to_string(index=False)
)

print("\n[이재모피자 주소의 동백전 가맹점]")

print(
    junggu_dongbaek[
        junggu_dongbaek['주소_정리'] == '부산 중구 광복중앙로 31'
    ][['가맹점 명', '주소_정리']].to_string(index=False)
)

# 미매칭 음식점 중 동백전 목록에 같은 상호명이 있는지 확인
same_name = unmatched_food.merge(
    junggu_dongbaek[
        ['가맹점 명', '상호명_정리', '주소_정리']
    ],
    on='상호명_정리',
    how='inner',
    suffixes=('_상가', '_동백전')
)

print("상호명 일치 후보 행 수:", len(same_name))

print("해당 음식점 수:", same_name['상가업소번호'].nunique())

print(
    same_name[
        ['상호명', '도로명주소', '가맹점 명', '주소_정리_동백전']
    ].head(15).to_string(index=False)
)

# 상가정보의 도로명에서 '부산광역시'를 '부산'으로 통일
same_name['도로명_정리'] = (
    same_name['도로명']
    .fillna('')
    .str.replace('부산광역시', '부산', regex=False)
    .str.strip()
)

# 동백전 주소가 동일한 도로명으로 시작하는지 확인
same_name['도로명_일치'] = same_name.apply(
    lambda row: (
        bool(row['도로명_정리'])
        and row['주소_정리_동백전'].startswith(
            row['도로명_정리'] + ' '
        )
    ),
    axis=1
)

road_candidates = same_name[
    same_name['도로명_일치']
].copy()

print("도로명 일치 후보 행 수:", len(road_candidates))
print(
    "도로명 일치 음식점 수:",
    road_candidates['상가업소번호'].nunique()
)

print(
    road_candidates[
        ['상호명', '도로명주소', '가맹점 명', '주소_정리_동백전']
    ].head(20).to_string(index=False)
)

# 1. 상가정보 지번주소 정리
unmatched_food['지번주소_정리'] = (
    unmatched_food['지번주소']
    .fillna('')
    .str.replace('부산광역시', '부산', regex=False)
    .str.replace(r'\s+', ' ', regex=True)
    .str.strip()
)

# 2. 상호명 + 지번주소 정확 일치
lot_matches = unmatched_food.merge(
    junggu_dongbaek[
        ['가맹점 명', '상호명_정리', '주소_정리']
    ],
    left_on=['상호명_정리', '지번주소_정리'],
    right_on=['상호명_정리', '주소_정리'],
    how='inner'
)

# 3. 결과 확인
print("지번주소 일치 행 수:", len(lot_matches))
print(
    "지번주소 일치 음식점 수:",
    lot_matches['상가업소번호'].nunique()
)

print(
    lot_matches[
        ['상호명', '지번주소', '가맹점 명', '주소_정리_y']
    ].head(20).to_string(index=False)
)

# STEP 10. 정확 일치 음식점 CSV 저장

# 1. 필요한 컬럼만 선택
final_food = exact_matches[
    [
        '상가업소번호',
        '상호명',
        '상권업종중분류명',
        '상권업종소분류명',
        '행정동명',
        '도로명주소',
        '지번주소',
        '위도',
        '경도',
        '가맹점 명'
    ]
].copy()

# 2. 중복 음식점 제거
final_food = final_food.drop_duplicates(
    subset='상가업소번호'
)

# 3. 매칭 상태 기록
final_food['매칭상태'] = '상호명+도로명주소 정확일치'

# 4. 저장 폴더 생성
OUTPUT_DIR = BASE_DIR / 'data' / 'processed'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 5. CSV 저장
output_path = OUTPUT_DIR / '남포광복_동백전_1차매칭.csv'

final_food.to_csv(
    output_path,
    index=False,
    encoding='utf-8-sig'
)

# 6. 결과 확인
print('저장된 음식점 수:', len(final_food))
print('저장 위치:', output_path)


print("\n[음식점 업종 분포]")
print(final_food['상권업종중분류명'].value_counts())

print("\n[위치정보 누락]")
print(final_food[['위도', '경도']].isna().sum())

print(
    final_food.groupby(
        ['상권업종중분류명', '상권업종소분류명']
    ).size().to_string()
)

# STEP 12. 관광객용 서비스 카테고리 생성

def classify_food(row):
    middle = row['상권업종중분류명']
    small = row['상권업종소분류명']

    if middle == '주점':
        return '주점'

    if small == '카페':
        return '카페'

    if small in [
        '김밥/만두/분식',
        '빵/도넛',
        '토스트/샌드위치/샐러드',
        '그 외 기타 간이 음식점'
    ]:
        return '간식·디저트'

    return '식사'


final_food['서비스분류'] = final_food.apply(
    classify_food, axis=1
)

print(final_food['서비스분류'].value_counts())

# STEP 13. 서비스 분류가 포함된 CSV 저장

output_path = OUTPUT_DIR / '남포광복_동백전_1차매칭.csv'

final_food.to_csv(
    output_path,
    index=False,
    encoding='utf-8-sig'
)

print("최종 저장 행 수:", len(final_food))
print("저장된 컬럼:", final_food.columns.tolist())
print("저장 완료:", output_path)

# STEP 14. 지역별 음식점 분포 확인

area_category = pd.crosstab(
    final_food['행정동명'],
    final_food['서비스분류']
)

print("\n[행정동별 서비스 분류]")
print(area_category)

print("\n[행정동별 전체 매장 수]")
print(final_food['행정동명'].value_counts())

# STEP 14-2. 음식점 위치 범위 확인

print("\n[전체 음식점 좌표 범위]")
print(
    final_food[['위도', '경도']].agg(
        ['min', 'max']
    )
)

print("\n[행정동별 평균 좌표]")
print(
    final_food.groupby('행정동명')[
        ['위도', '경도']
    ].mean()
)

# STEP 15. 시연용 음식점 후보 추출

candidate_counts = {
    '식사': 20,
    '카페': 15,
    '간식·디저트': 15,
    '주점': 5
}

candidate_list = []

for category, count in candidate_counts.items():
    group = final_food[
        final_food['서비스분류'] == category
    ]

    selected = group.sample(
        n=min(count, len(group)),
        random_state=42
    )

    candidate_list.append(selected)

candidates = pd.concat(
    candidate_list,
    ignore_index=True
)

print("후보 음식점 수:", len(candidates))

print(
    candidates[
        ['상호명', '행정동명', '서비스분류', '도로명주소']
    ].to_string(index=False)
)

# STEP 16. 시연용 후보 검토 파일 생성

review = candidates.copy()

review['영업확인'] = '미확인'
review['동백전결제확인'] = '추가확인필요'
review['대표메뉴'] = ''
review['메뉴가격'] = ''
review['선정여부'] = '검토중'
review['확인출처'] = ''

review_path = OUTPUT_DIR / '시연용_55곳_검토목록.csv'

review.to_csv(
    review_path,
    index=False,
    encoding='utf-8-sig'
)

print('검토용 후보 수:', len(review))
print('저장 완료:', review_path)
