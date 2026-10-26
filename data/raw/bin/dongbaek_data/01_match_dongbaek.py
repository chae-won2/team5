import pandas as pd

# 동백전 가맹점 데이터 불러오기
dongbaek = pd.read_csv(
    "data/raw/부산광역시_지역화폐(동백전) 가맹점 현황_20260424.csv",
    encoding="utf-8-sig"
)

# 중구 음식업 데이터 불러오기
food = pd.read_csv(
    "data/processed/중구_음식 - 중구_음식 (2).csv",
    encoding="utf-8-sig"
)

# 데이터 행 개수 확인
print("동백전 가맹점:", len(dongbaek))
print("중구 음식업:", len(food))
print(food['행정동명'].value_counts())
target_dongs = ['남포동', '광복동']

nampo_food = food[
    food['행정동명'].isin(target_dongs)
].copy()

print("남포·광복 음식점:", len(nampo_food))
print(
    nampo_food[
        ['상호명', '행정동명', '상권업종중분류명', '도로명주소']
    ].head(10)
)
import re

def clean_address(address):
    if pd.isna(address):
        return ""

    address = str(address)

    # 부산광역시 → 부산
    address = address.replace("부산광역시", "부산")

    # 연속된 공백을 하나로 통일
    address = re.sub(r"\s+", " ", address)

    return address.strip()
dongbaek['주소_정리'] = dongbaek['주소'].apply(clean_address)

nampo_food['주소_정리'] = nampo_food['도로명주소'].apply(clean_address)
print("동백전 주소:")
print(dongbaek[['주소', '주소_정리']].head(5))

print("\n남포·광복 음식점 주소:")
print(nampo_food[['도로명주소', '주소_정리']].head(5))
junggu_dongbaek = dongbaek[
    dongbaek['주소_정리'].str.startswith('부산 중구 ')
].copy()

print("중구 동백전 가맹점:", len(junggu_dongbaek))
matched = nampo_food.merge(
    junggu_dongbaek[['가맹점 명', '주소_정리']],
    on='주소_정리',
    how='left'
)

print("주소 매칭 결과 행 수:", len(matched))
print("주소 일치 후보 행 수:", matched['가맹점 명'].notna().sum())
print(
    matched[
        ['상호명', '가맹점 명', '주소_정리']
    ].head(10).to_string(index=False)
)
def clean_name(name):
    if pd.isna(name):
        return ""

    name = str(name).lower()
    name = re.sub(r"[^가-힣a-z0-9]", "", name)

    return name
matched['상호명_정리'] = matched['상호명'].apply(clean_name)
matched['가맹점명_정리'] = matched['가맹점 명'].apply(clean_name)
from difflib import SequenceMatcher

def name_similarity(row):
    name1 = row['상호명_정리']
    name2 = row['가맹점명_정리']

    if not name1 or not name2:
        return 0.0

    return SequenceMatcher(None, name1, name2).ratio()

matched['이름유사도'] = matched.apply(
    name_similarity,
    axis=1
)
top_matches = matched.sort_values(
    '이름유사도',
    ascending=False
)

print(
    top_matches[
        ['상호명', '가맹점 명', '주소_정리', '이름유사도']
    ].head(20).to_string(index=False)
)
best_matches = (
    matched
    .sort_values('이름유사도', ascending=False)
    .drop_duplicates(subset='상가업소번호', keep='first')
    .copy()
)

print("음식점 수:", len(best_matches))
print("완전 일치:",
      (best_matches['이름유사도'] == 1.0).sum())

print("0.8 이상:",
      (best_matches['이름유사도'] >= 0.8).sum())

print("0.6 이상:",
      (best_matches['이름유사도'] >= 0.6).sum())

print("0.4 이상:",
      (best_matches['이름유사도'] >= 0.4).sum())

print("0.4 미만:",
      (best_matches['이름유사도'] < 0.4).sum())
print(
    pd.cut(
        best_matches['이름유사도'],
        bins=[-0.01, 0.4, 0.6, 0.8, 1.0],
        labels=['0.4 미만', '0.4~0.6', '0.6~0.8', '0.8~1.0']
    ).value_counts().sort_index()
)
# 상가정보 원본에서 투썸부산 확인
print(
    food[food['상호명'] == '투썸부산'][
        ['상가업소번호', '상호명', '도로명주소', '지번주소']
    ].to_string(index=False)
)

# 동백전 원본에서 같은 주소의 가맹점 확인
print(
    dongbaek[
        dongbaek['주소_정리'] == '부산 중구 구덕로 40'
    ][
        ['가맹점 명', '주소']
    ].to_string(index=False)
)