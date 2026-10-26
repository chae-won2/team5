"""Separate missing/non-numeric prices; accept manually collected numeric prices without evidence checks."""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]+)?|[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?)')

def price_issue(value):
    value = str('' if value is None else value).strip()
    if not value:
        return '가격 없음'
    return '' if NUMBER.fullmatch(value) else '가격에 문자·비숫자 포함'

def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.csv.tmp')
    with temp.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)

def main(source):
    with source.open(encoding='utf-8-sig',newline='') as f:
        reader = csv.DictReader(f)
        fields, rows = reader.fieldnames, list(reader)
    if '1인 가격(원)' not in fields:
        raise ValueError('Missing price column')
    accepted, review = [], []
    for row in rows:
        reason = price_issue(row['1인 가격(원)'])
        if reason:
            review.append({**row, '분리 사유':reason})
        else:
            accepted.append(row)
    assert len(rows) == len(accepted) + len(review)
    output = ROOT/'data/processed/estimated_spend'
    write_csv(output/'merchant_spend_400_cleaned.csv',accepted,fields)
    write_csv(output/'merchant_spend_400_price_review.csv',review,fields+['분리 사유'])
    print('숫자 가격 기록:',len(accepted))
    print('분리 기록:',len(review),dict(Counter(row['분리 사유'] for row in review)))

if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,nargs='?',default=ROOT/'data/raw/estimated_spend/merchant_spend_400_original.csv')
    main(parser.parse_args().source)
