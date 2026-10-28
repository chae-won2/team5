"""지역상생 운영 대시보드: 상권 현황 · 추천 노출 성과 · 데이터 신뢰성.
대상은 지역상생 사업담당자·서비스 운영자이며 익명 집계만 다룬다. 공개 화면과 별도로 키로 보호한다."""

import os
from html import escape
from secrets import compare_digest

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.data_loader import load_places, load_opening_hours
from app.services.exposure import summary, window_summary, ExposureStorageError
from app.services.place_tags import normalized

router = APIRouter(tags=["admin"])

ADMIN_DASHBOARD_KEY = os.environ.get("ADMIN_DASHBOARD_KEY")


def _top5_share(data):
    rows = sorted(data["places"].items(), key=lambda item: item[1][1], reverse=True)
    total = sum(total for _, total in data["places"].values())
    top5 = sum(total for _, (_, total) in rows[:5])
    return (top5 / total) if total else 0


def _delta(current, baseline, *, points=False):
    """Real (not fabricated) trend badge: vs a previous window computed from actual exposure history."""
    if baseline == 0:
        return ("일정", "flat") if current == 0 else ("신규", "up")
    diff = (current - baseline) if points else (current - baseline) / baseline
    cls = "flat" if diff == 0 else ("up" if diff > 0 else "down")
    return f"{diff:+.0%}" + ("p" if points else ""), cls


def _kpi_cards(places, data, prev, trailing):
    avg_requests = sum(w["requests_total"] for w in trailing) / len(trailing)
    avg_shown = sum(w["requests_shown"] for w in trailing) / len(trailing)
    avg_top5 = sum(_top5_share(w) for w in trailing) / len(trailing)
    top5_now = _top5_share(data)
    cards = [
        ("추천 요청 수", "최근 7일간 카테고리 추천이 몇 번 요청됐는지 확인할 수 있어요.", f"{data['requests_total']}건",
         _delta(data['requests_total'], prev['requests_total']), _delta(data['requests_total'], avg_requests)),
        ("표시 확인 수", "추천 목록이 실제로 화면에 노출된 횟수예요.", f"{data['requests_shown']}건",
         _delta(data['requests_shown'], prev['requests_shown']), _delta(data['requests_shown'], avg_shown)),
        ("상위 5곳 노출 집중도", "추천이 일부 가맹점에만 쏠리는지 확인할 수 있어요.", f"{top5_now:.0%}",
         _delta(top5_now, _top5_share(prev), points=True), _delta(top5_now, avg_top5, points=True)),
        ("서비스 등록 장소 수", "원도심 가맹점·관광명소 데이터 규모예요.", f"{len(places)}곳",
         ("일정", "flat"), ("일정", "flat")),
    ]
    body = "".join(f"""<div class="kpi-card">
<h3>{escape(title)}</h3>
<p class="kpi-desc">{escape(desc)}</p>
<div class="kpi-value">{value}</div>
<div class="kpi-row">지난 7일 대비 <span class="badge {week_cls}">{week_text}</span></div>
<div class="kpi-row">지난 4주 평균 대비 <span class="badge {avg_cls}">{avg_text}</span></div>
</div>""" for title, desc, value, (week_text, week_cls), (avg_text, avg_cls) in cards)
    return f"""
<section id="kpi">
<h2>요약 지표</h2>
<p class="caption">추천 요청·노출·데이터 규모를 한눈에 확인해 서비스 관심도와 지역상생 효과를 파악할 수 있어요.</p>
<div class="kpi-grid">{body}</div>
</section>"""


def _market_overview(places):
    districts = sorted(places.district.unique())
    categories = sorted(places.category.unique())
    counts = places.pivot_table(index="district", columns="category", values="id", aggfunc="count", fill_value=0)
    by_district = places.district.value_counts()
    top_district, top_count = by_district.idxmax(), by_district.max()
    rows = "".join(
        f"<tr><td>{escape(d)}</td>" + "".join(f"<td>{int(counts.loc[d, c])}</td>" for c in categories)
        + f"<td>{int(by_district[d])}</td></tr>"
        for d in districts
    )
    payment = places.payment_status.value_counts()
    return f"""
<section id="market">
<h2>화면 1 · 지역상권 현황</h2>
<p class="caption">가맹점·명소가 어느 지역과 업종에 집중되어 있는지 — 지역은행의 소상공인 고객 기반·상권 이해 업무에 연결.</p>
<p>전체 {len(places)}곳 · 최다 집중 지역 <b>{escape(top_district)}</b> {int(top_count)}곳 ({top_count / len(places):.0%})</p>
<table>
<tr><th>지역</th>{"".join(f"<th>{escape(c)}</th>" for c in categories)}<th>합계</th></tr>
{rows}
</table>
<p>동백전 결제 상태 — 가맹점 등재 {payment.get('merchant_listed', 0)}곳 · 미확인 {payment.get('not_verified', 0)}곳 · 결제 불가 {payment.get('not_accepted', 0)}곳</p>
</section>"""


def _exposure_performance(places, data):
    names = dict(zip(places.id, places.name))
    rows = sorted(data["places"].items(), key=lambda item: item[1][1], reverse=True)
    total_exposure = sum(total for _, total in data["places"].values())
    top5_share = _top5_share(data)
    body = "".join(
        f"<tr><td>{escape(names.get(place_id, place_id))}</td><td>{top}</td><td>{total}</td>"
        f"<td>{(total / total_exposure):.0%}</td></tr>"
        for place_id, (top, total) in rows[:10]
    ) or "<tr><td colspan='4'>최근 7일 표시 확인 기록 없음</td></tr>"
    return f"""
<section id="rotation">
<h2>화면 2 · 지역상생 추천 성과</h2>
<p class="caption">추천이 일부 가맹점에만 노출을 집중시키는지 검증 — 지역화폐 가맹점 홍보 기회·상생 정책 운영 성과 분석에 연결 (추천 로그 기준, 최근 7일).</p>
<p>추천 요청 {data['requests_total']}건 · 표시 확인 {data['requests_shown']}건 · 후보 0곳 요청 {data['requests_empty']}건</p>
<p>상위 5곳 노출 집중도: 전체 노출의 <b>{top5_share:.0%}</b> ({'노출 상위권이 고르게 분산' if top5_share < 0.5 or total_exposure == 0 else '소수 가맹점에 집중'})</p>
<!-- shortcut: 50% 기준은 임의 판단. 실제 운영 기준값이 정해지면 교체 -->

<table>
<tr><th>장소</th><th>1위 노출</th><th>전체 노출</th><th>비중</th></tr>
{body}
</table>
</section>"""


def _data_quality(places):
    opened = load_opening_hours().place_id.nunique()
    spend_missing = int(places.estimated_spend.isna().sum())
    attractions = places[places.category == "관광명소"]
    admission_unknown = int((attractions.admission_fee_status == "unknown").sum())
    name_key = places.name.map(normalized)
    name_dup_groups = places.assign(_k=name_key).duplicated(subset=["_k", "admin_dong"], keep=False).sum()
    coord_dup = places.duplicated(subset=["lat", "lon"], keep=False)
    coord_dup_places = int(coord_dup.sum())
    coord_dup_groups = places[coord_dup].groupby(["lat", "lon"]).ngroups
    return f"""
<section id="quality">
<h2>화면 3 · 데이터 신뢰성 관리</h2>
<p class="caption">중복·좌표 공유·정보 누락을 분석 — 금융권 업무지원의 정확성·오류 예방·데이터 검증 역량과 연결.</p>
<table>
<tr><th>항목</th><th>건수</th><th>비율</th></tr>
<tr><td>영업시간 정보 보유</td><td>{opened}</td><td>{opened / len(places):.0%}</td></tr>
<tr><td>예상지출 정보 결측</td><td>{spend_missing}</td><td>{spend_missing / len(places):.0%}</td></tr>
<tr><td>관광명소 입장료 상태 미확인</td><td>{admission_unknown}</td><td>{(admission_unknown / len(attractions) if len(attractions) else 0):.0%} (관광명소 {len(attractions)}곳 중)</td></tr>
<tr><td>같은 상호·행정동 중복 후보</td><td>{int(name_dup_groups)}곳</td><td>-</td></tr>
<tr><td>좌표를 다른 장소와 완전히 공유</td><td>{coord_dup_places}곳</td><td>{coord_dup_groups}개 그룹 (지오코딩 대표좌표 추정)</td></tr>
</table>
</section>"""


@router.get("/admin", response_class=HTMLResponse)
def dashboard(key: str = ""):
    if not ADMIN_DASHBOARD_KEY:
        raise HTTPException(500, "ADMIN_DASHBOARD_KEY가 설정되어 있지 않습니다.")
    if not compare_digest(key, ADMIN_DASHBOARD_KEY):
        raise HTTPException(403, "key가 올바르지 않습니다.")

    try:
        places = load_places()
        data = summary()
        prev = window_summary(1)
        trailing = [window_summary(w) for w in range(1, 5)]
        sections = (_kpi_cards(places, data, prev, trailing) + _market_overview(places)
                    + _exposure_performance(places, data) + _data_quality(places))
    except ExposureStorageError as error:
        raise HTTPException(503, str(error)) from None

    return HTMLResponse(f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><title>지역상생 운영 대시보드 · 부산 풀코스</title>
<style>
@font-face {{ font-family:"Busan Dandi Gothic"; src:url("/fonts/BusanDandiGothic-M.woff2") format("woff2"); font-weight:400 500; font-display:swap; }}
@font-face {{ font-family:"Busan Dandi Gothic"; src:url("/fonts/BusanDandiGothic-B.woff2") format("woff2"); font-weight:600 700 800 900; font-display:swap; }}
:root {{
  --primary:#237e68; --primary-dark:#17604e; --primary-light:#edf6f0;
  --bg:#eef2ef; --surface:#ffffff; --border:#e5ebe6;
  --text:#243e32; --text-muted:#7d8e83;
  --shadow-sm:0 1px 2px rgba(15,23,42,.06); --shadow-md:0 4px 16px rgba(15,23,42,.08);
  --sans:"Busan Dandi Gothic","Pretendard Variable",-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,sans-serif;
}}
* {{ box-sizing: border-box; }}
body {{ font-family: var(--sans); margin: 0; background: var(--bg); color: var(--text); }}
.admin-header {{ display:flex; align-items:center; gap:16px; padding:0 30px; height:76px; background:var(--surface); border-bottom:1px solid var(--border); }}
.admin-header img {{ height:36px; }}
.admin-badge {{ margin-left:auto; display:inline-flex; align-items:center; border:1px solid var(--border); border-radius:999px; background:var(--primary-light); color:var(--primary-dark); font-size:12px; font-weight:700; padding:6px 14px; }}
main {{ max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
nav.toc {{ display:flex; gap:10px; margin: 18px 0 30px; }}
nav.toc a {{ color: var(--primary-dark); text-decoration:none; font-size:13px; font-weight:700; background:var(--surface); border:1px solid var(--border); border-radius:999px; padding:7px 14px; }}
section {{ background: var(--surface); border:1px solid var(--border); border-radius:16px; box-shadow: var(--shadow-sm); padding:22px 24px; margin-bottom: 22px; }}
h2 {{ font-size:16px; color: var(--primary-dark); margin:0 0 6px; }}
.caption {{ color: var(--text-muted); font-size:13px; margin-bottom:12px; }}
table {{ border-collapse: collapse; width:100%; margin: 10px 0 4px; font-size:13px; }}
td, th {{ border: 1px solid var(--border); padding: 7px 12px; text-align: right; }}
th {{ background: var(--primary-light); color: var(--primary-dark); }}
th:first-child, td:first-child {{ text-align: left; }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-top:14px; }}
.kpi-card {{ border:1px solid var(--border); border-radius:14px; padding:18px; }}
.kpi-card h3 {{ font-size:14px; margin:0 0 4px; }}
.kpi-desc {{ color:var(--text-muted); font-size:12px; margin-bottom:14px; min-height:32px; }}
.kpi-value {{ font-size:28px; font-weight:800; margin-bottom:14px; }}
.kpi-row {{ display:flex; align-items:center; justify-content:space-between; font-size:12px; color:var(--text-muted); margin-top:8px; }}
.badge {{ border-radius:999px; padding:3px 9px; font-weight:700; font-size:11px; }}
.badge.up {{ background:#eef1ff; color:#3452e0; }}
.badge.down {{ background:#fdecef; color:#d93a56; }}
.badge.flat {{ background:#f1f3f2; color:#6b7a72; }}
@media(max-width:760px) {{ .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} }}
</style></head><body>
<header class="admin-header">
<img src="/busan-full-course-logo.png" alt="부산 풀코스 · BUSAN FULL COURSE">
<span class="admin-badge">운영자 대시보드</span>
</header>
<main>
<h1>지역상생 운영 대시보드</h1>
<p class="caption">부산 풀코스 서비스의 상권·추천·데이터 현황을 운영자 전용으로 집계합니다.</p>
<nav class="toc"><a href="#kpi">요약 지표</a><a href="#market">1. 지역상권 현황</a><a href="#rotation">2. 추천 성과</a><a href="#quality">3. 데이터 신뢰성</a></nav>
{sections}
</main>
</body></html>""")
