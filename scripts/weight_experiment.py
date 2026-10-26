"""Separate weighting experiment; never changes the service catalog.

prepare: select 40 reproducible places and query TMAP for new places.
score: calculate scores from a CSV containing storage-permitted ratings.
"""
import argparse
import csv
import math
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.services.walking import walking_leg, WalkingError

WEIGHTS = {'식당': .75, '카페·디저트': .70, '관광명소': 1., '쇼핑': 1.}
TARGETS = {'식당': 17, '카페·디저트': 17, '관광명소': 3, '쇼핑': 3}
OUT = ROOT / 'data/bin/experiments/weights_v01'


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def score(rating, count, mean, minutes, weight, m=20):
    values = (rating, count, mean, minutes, weight, m)
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite score input')
    if not (1 <= rating <= 5 and 1 <= mean <= 5 and count > 0
            and count.is_integer() and minutes >= 0 and 0 <= weight <= 1 and m > 0):
        raise ValueError('Invalid score input')
    adjusted = (count * rating + m * mean) / (count + m)
    distance = max(0., 1 - minutes / 20)
    total = weight * (adjusted - 1) / 4 + (1 - weight) * distance
    return adjusted, distance, total if minutes <= 20 else None


def select_sample(places):
    selected = []
    for category, target in TARGETS.items():
        rng = random.Random(f'20261023:{category}')
        groups = defaultdict(list)
        for p in sorted(places, key=lambda p: p['id']):
            if p['category'] == category:
                groups[p['admin_dong']].append(p)
        for group in groups.values():
            rng.shuffle(group)
        chosen = []
        while len(chosen) < target and any(groups.values()):
            for dong in sorted(groups):
                if groups[dong] and len(chosen) < target:
                    chosen.append(groups[dong].pop())
        if len(chosen) != target:
            raise ValueError(f'Not enough places in category: {category}')
        selected.extend(chosen)
    return selected


def prepare():
    path = OUT / 'sample.csv'
    existing = read(path) if path.exists() else []
    if len({r['id'] for r in existing}) != len(existing):
        raise SystemExit('Duplicate sample IDs.')
    load_dotenv(ROOT / '.env')
    if existing:
        station = {'place_name': existing[0]['start_name'],
                   'y': existing[0]['start_lat'], 'x': existing[0]['start_lon']}
    else:
        response = requests.get('https://dapi.kakao.com/v2/local/search/keyword.json',
                            headers={'Authorization': 'KakaoAK ' + os.environ['KAKAO_REST_API_KEY']},
                            params={'query': '남포역'}, timeout=15)
        if not response.ok:
            raise SystemExit('Departure search failed (credentials not logged).')
        stations = [p for p in response.json().get('documents', [])
                if p['category_group_code'] == 'SW8' and '남포역' in p['place_name']]
        if len(stations) != 1:
            raise SystemExit('Departure station could not be uniquely identified.')
        station = stations[0]
    lat, lon = float(station['y']), float(station['x'])
    places = read(ROOT / 'data/processed/fin/places.csv')
    selected = select_sample(places)
    selected_ids = {p['id'] for p in selected}
    if any(r['id'] not in selected_ids and any(r[k] for k in ('rating', 'review_count', 'rating_source'))
           for r in existing):
        raise SystemExit('Existing rating entries would be removed; preserve them before resampling.')
    cached = {r['id']: r for r in existing}
    rows = []
    reused = 0
    for p in selected:
        old = cached.get(p['id'])
        if old and all(float(old[k]) == float(v) for k, v in
                       [('start_lat', lat), ('start_lon', lon), ('lat', p['lat']), ('lon', p['lon'])]) \
                and old['walk_minutes']:
            rows.append(old)
            reused += 1
            continue
        try:
            leg = walking_leg(lat, lon, float(p['lat']), float(p['lon']))
            minutes = leg['leg_seconds'] / 60
            status = 'awaiting_rating' if minutes <= 20 else 'outside_20min'
        except WalkingError:
            minutes, status = '', 'walking_lookup_failed'
        rows.append({k: p[k] for k in ('id', 'name', 'category', 'admin_dong', 'address', 'lat', 'lon')}
                    | {'start_name': station['place_name'], 'start_lat': lat, 'start_lon': lon,
                       'walk_minutes': minutes, 'rating': '', 'review_count': '',
                       'rating_source': '', 'status': status})
    write(path, rows)
    print(f'Prepared {len(rows)} places; walkable: {sum(r["status"] == "awaiting_rating" for r in rows)}; '
          f'walking failures: {sum(r["status"] == "walking_lookup_failed" for r in rows)}; reused: {reused}')


def calculate(path):
    rows = read(path)
    means = defaultdict(list)
    for r in rows:
        if r['rating'] and r['review_count'] and float(r['review_count']) > 0:
            if not r.get('rating_source'):
                raise ValueError('Rating source is required')
            score(float(r['rating']), float(r['review_count']), float(r['rating']), 0., 1.)
            means[r['category']].append(float(r['rating']))
    for r in rows:
        r.update(category_mean='', adjusted_rating='', distance_score='', final_score='', rank='')
        if not r['walk_minutes']:
            r['status'] = 'walking_lookup_failed'
        elif float(r['walk_minutes']) > 20:
            r['status'] = 'outside_20min'
        elif not r['rating'] or not r['review_count'] or float(r['review_count']) == 0:
            r['status'] = 'awaiting_rating'
        else:
            mean = sum(means[r['category']]) / len(means[r['category']])
            adjusted, distance, total = score(float(r['rating']), float(r['review_count']),
                                               mean, float(r['walk_minutes']), WEIGHTS[r['category']])
            r.update(category_mean=mean, adjusted_rating=adjusted, distance_score=distance,
                     final_score=total, status='scored')
    for category in WEIGHTS:
        ranked = sorted([r for r in rows if r['category'] == category and r['status'] == 'scored'],
                        key=lambda r: (-r['final_score'], r['id']))
        for rank, r in enumerate(ranked, 1):
            r['rank'] = rank
    write(OUT / 'scores.csv', rows)
    print(f'Scored {sum(r["status"] == "scored" for r in rows)}/{len(rows)}; missing values remain blank.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'score', 'check'])
    parser.add_argument('--input', type=Path, default=OUT / 'sample.csv')
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare()
    elif args.mode == 'score':
        calculate(args.input)
    else:
        a, d, total = score(4.8, 10., 4.2, 10., .75)
        assert abs(a - 4.4) < 1e-10 and d == .5 and abs(total - .7625) < 1e-10
        assert score(4.8, 10., 4.2, 20.01, 1.)[2] is None
        assert score(4.8, 10., 4.2, 20., 1.)[2] is not None
        assert score(4.8, 10., 4.2, 0., 1.)[2] == score(4.8, 10., 4.2, 19., 1.)[2]
        places = read(ROOT / 'data/processed/fin/places.csv')
        sample = select_sample(places)
        assert sample == select_sample(list(reversed(places)))
        assert len(sample) == len({p['id'] for p in sample}) == 40
        for category, target in TARGETS.items():
            group = [p for p in sample if p['category'] == category]
            assert len(group) == target
            if target == 17:
                counts = [sum(p['admin_dong'] == d for p in group)
                          for d in ('남포동', '광복동', '부평동', '대청동')]
                assert sorted(counts) == [4, 4, 4, 5]
        print('Formula, boundary, fixed allocation and reproducibility checks passed.')
