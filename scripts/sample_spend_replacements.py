"""Draw new MVP merchants for the 39 missing-price slots without reusing the original 400."""
import csv
import random
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = '20261026:spend-replacement39'

def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def identity(name,address):
    return (re.sub(r'\s+','',name).casefold(), re.sub(r'\s+','',address.replace('부산광역시','부산')))

def main():
    original = read(ROOT/'data/raw/estimated_spend/merchant_spend_400_original.csv')
    missing = read(ROOT/'data/processed/estimated_spend/merchant_spend_400_price_review.csv')
    places = read(ROOT/'data/processed/fin/places.csv')
    assert len(missing)==39
    excluded = {r['장소 ID'] for r in original}
    identities = {identity(r['상호명'],r['주소']) for r in original}
    pool = [p for p in places if p['id'] not in excluded and p['payment_status']=='merchant_listed'
            and p['category'] in {'식당','카페·디저트'} and p['admin_dong'] in {'남포동','광복동','부평동','대청동'}
            and identity(p['name'],p['address']) not in identities]
    pool.sort(key=lambda p:p['id'])
    random.Random(SEED).shuffle(pool)
    used = set()
    assignments = {}
    def assign(index, candidates):
        for place in candidates:
            if place['id'] not in used:
                assignments[index]=place
                used.add(place['id'])
                return True
        return False
    # Reserve exact dong/category matches first, before assigning scarce cross-dong cafes.
    for i,old in enumerate(missing):
        assign(i,[p for p in pool if p['admin_dong']==old['행정동'] and p['category']==old['카테고리']])
    for i,old in enumerate(missing):
        if i not in assignments:
            assign(i,[p for p in pool if p['category']==old['카테고리']])
    for i,old in enumerate(missing):
        if i not in assignments:
            assign(i,[p for p in pool if p['admin_dong']==old['행정동']])
    for i in range(len(missing)):
        if i not in assignments and not assign(i,pool):
            raise ValueError('Not enough distinct replacement merchants')
    output=[]
    for i,old in enumerate(missing):
        p=assignments[i]
        row={key:'' for key in list(original[0])[:24]}
        row.update({'번호':i+1,'장소 ID':p['id'],'상호명':p['name'],'카테고리':p['category'],
                    '행정동':p['admin_dong'],'주소':p['address'],'위도':p['lat'],'경도':p['lon'],
                    '장소 유형':p['visit_type'],'기본 체류시간(분)':p['duration_min'],
                    '동백전 가맹점':'명부 등재','원본 기준일':p['data_date'],'원천':p['source'],
                    '상태':'미조사'})
        changes=[]
        if p['admin_dong']!=old['행정동']: changes.append('기존 행정동 후보 부족으로 타 MVP 동 배정')
        if p['category']!=old['카테고리']: changes.append('신규 카페·디저트 후보 부족으로 식당 배정')
        row.update({'교체 대상 ID':old['장소 ID'],'교체 대상 상호명':old['상호명'],
                    '교체 대상 행정동':old['행정동'],'교체 대상 카테고리':old['카테고리'],
                    '배정 사유':'; '.join(changes) if changes else '동일 행정동·카테고리 대체',
                    '추출 시드':SEED})
        output.append(row)
    assert len(output)==len({p['장소 ID'] for p in output})==39
    assert not used & excluded
    assert all(not p['1인 가격(원)'] for p in output)
    path=ROOT/'data/processed/estimated_spend/merchant_spend_39_new_survey.csv'
    if path.exists() and any(row.get('상태') != '미조사' or row.get('1인 가격(원)') for row in read(path)):
        raise FileExistsError('Survey contains research results; preserve it before drawing again.')
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    print('New survey:',len(output))
    print('Category:',dict(Counter(p['카테고리'] for p in output)))
    print('Dong:',dict(Counter(p['행정동'] for p in output)))
    print('Changed category:',sum(p['카테고리']!=p['교체 대상 카테고리'] for p in output))
    print('CSV:',path)

if __name__=='__main__': main()
