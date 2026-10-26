import pandas as pd
from pathlib import Path

# 프로젝트 폴더 경로
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data' / 'processed'

# CSV 불러오기
candidates = pd.read_csv(
    DATA_DIR / '시연용_55곳_검토목록.csv',
    encoding='utf-8-sig'
)

details = pd.read_csv(
    DATA_DIR / '시연용_10곳_상세정보.csv',
    encoding='utf-8-sig'
)

# 병합 전 중복 및 누락 확인
print("55곳 후보:", len(candidates))
print("상세정보:", len(details))
print("후보 상호명 중복:", candidates['상호명'].duplicated().sum())
print("상세정보 상호명 중복:", details['상호명'].duplicated().sum())

missing = details.loc[
    ~details['상호명'].isin(candidates['상호명']),
    '상호명'
]
print("후보 목록에서 찾지 못한 매장:", missing.tolist())

# 상호명을 기준으로 병합
demo = candidates.merge(
    details,
    on='상호명',
    how='inner',
    validate='one_to_one',
    suffixes=('_후보', '')
)
# 야키토리기원 서비스 분류 수정
demo.loc[
    demo['상호명'] == '야키토리기원',
    '서비스분류'
] = '주점'

print("\n병합 결과:", len(demo), "곳")

print(
    demo[
        ['상호명', '서비스분류', '위도', '경도', '대표메뉴', '메뉴가격']
    ].to_string(index=False)
)

# STEP 20. 지도용 최종 데이터 저장

output_path = DATA_DIR / '시연용_10곳_지도데이터.csv'

demo.to_csv(
    output_path,
    index=False,
    encoding='utf-8-sig'
)

print("\n지도용 데이터 저장 완료:", output_path)
print("매장 수:", len(demo))

print(
    demo.loc[
        demo['상호명'] == '야키토리기원',
        ['상호명', '서비스분류']
    ]
)