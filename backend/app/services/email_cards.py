"""Table-based transactional email using the planner's sea-blue palette."""
from html import escape
import math
import os
from urllib.parse import urlencode

from app.data_loader import load_places
from app.services.place_labels import identity_text, official_labels, romanized_name


def render_email(req):
    from app.routers.notify import EMAIL_COPY, build_course_link, format_duration, schedule_range
    text = EMAIL_COPY[req.language]
    c = text['card']
    h = lambda value: escape(str(value), quote=True)
    primary, dark, pale, border, muted = '#176b9c', '#104e75', '#edf6fc', '#dfe8ef', '#647e91'
    catalog = {row['id']: row for row in load_places().to_dict('records')}
    timed = bool(req.departure_time) and all((s.leg_seconds is not None or s.leg_minutes is not None) and s.duration_min is not None for s in req.stops)
    walk_known = all(s.leg_seconds is not None or s.leg_minutes is not None for s in req.stops) and (not req.return_to_start or req.return_seconds is not None or req.return_minutes is not None)
    elapsed, walk_seconds, prices, rows = 0.0, 0.0, [], []

    def line(value, color=muted):
        return f'<p style="margin:7px 0 0;color:{color};font-size:12px;line-height:1.7">{h(value)}</p>'

    for index, stop in enumerate(req.stops):
        row = catalog.get(stop.id, {})
        if row and (identity_text(row['name']) != identity_text(stop.name) or identity_text(row['address']) != identity_text(stop.address)):
            row = {}
        official = official_labels(stop.id, stop.name, stop.address, req.language)
        name, address = official.get('name') or stop.name, official.get('address') or stop.address
        seconds = stop.leg_seconds if stop.leg_seconds is not None else stop.leg_minutes * 60 if stop.leg_minutes is not None else None
        walk_window, visit_window = '', ''
        if seconds is not None:
            walk_seconds += seconds
        if timed:
            walk_window = schedule_range(req.departure_time, elapsed, elapsed + seconds, text)
            elapsed += seconds
            visit_window = schedule_range(req.departure_time, elapsed, elapsed + stop.duration_min * 60, text)
            elapsed += stop.duration_min * 60
        walking = text['walk'].format(n=format_duration(seconds / 60, text)) if seconds is not None else c['walking_unknown']
        if walk_window:
            walking += ' (' + walk_window + ')'
        reading = romanized_name(stop.name) if req.language != 'ko' and not official.get('name') else ''
        details = line(f"{text['native_name']}: {stop.name}") if name != stop.name else ''
        if reading:
            details += line(text['romanized_name'] + ': ' + reading)
        details += line(address)
        if address != stop.address:
            details += line(text['native_address'] + ': ' + stop.address)
        if stop.duration_min is not None:
            details += line(text['stay'].format(n=format_duration(stop.duration_min, text)), dark)
        amount = row.get('estimated_spend')
        if stop.category in ['식당','카페·디저트','카페/디저트']:
            if isinstance(amount, (int, float)) and math.isfinite(amount) and amount >= 0:
                prices.append(amount)
                details += line(c['spend'].format(amount=f'{amount:,.0f}'), primary)
            else:
                details += line(c['price_unknown'])
        if stop.category == '관광명소':
            status, fee = row.get('admission_fee_status'), row.get('admission_fee_krw')
            if status == 'free':
                details += line(c['free'], primary)
            elif status == 'paid' and isinstance(fee, (int, float)) and math.isfinite(fee):
                details += line(c['admission'].format(amount=f'{fee:,.0f}'), primary)
                if row.get('admission_fee_note'):
                    details += line(row['admission_fee_note'])
            elif status == 'conditional':
                details += line(c['fee_check'])
        payment = {'merchant_listed':c['payment_listed'], 'not_accepted':c['payment_no']}.get(row.get('payment_status'), c['payment_check'])
        details += line(payment, primary if row.get('payment_status') == 'merchant_listed' else muted)
        map_url = 'https://www.google.com/maps/dir/?' + urlencode({'api':'1','destination':stop.address + ' ' + stop.name,'travelmode':'walking'})
        category = text['categories'].get(stop.category, stop.category)
        rows.append(f'''<tr><td style="width:30px;vertical-align:top;padding-top:35px"><span style="display:inline-block;width:24px;height:24px;line-height:24px;background:{primary};color:#fff;border-radius:50%;text-align:center;font-size:12px">{index+1}</span></td><td style="padding:0 0 18px 8px">
<p style="margin:0 0 10px;font-size:12px;line-height:1.6;color:{muted}">{h(walking)}</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid {border};border-radius:14px"><tr><td style="padding:18px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0"><tr><td style="color:{primary};font-size:12px;line-height:1.6">{h(visit_window)}</td><td align="right" style="font-size:11px;color:{muted}">{h(category)}</td></tr></table>
<h2 style="margin:9px 0 0;font-size:17px;line-height:1.5;color:#203b50;overflow-wrap:anywhere">{h(name)}</h2>{details}
<p style="margin:12px 0 0;text-align:right"><a href="{h(map_url)}" style="font-size:12px;color:{primary};text-decoration:none">{h(c['maps'])} &#8594;</a></p>
</td></tr></table></td></tr>''')
    if req.return_to_start:
        seconds = req.return_seconds if req.return_seconds is not None else req.return_minutes * 60 if req.return_minutes is not None else None
        value = text['return'].format(n=format_duration(seconds / 60 if seconds is not None else None,text))
        if seconds is not None:
            walk_seconds += seconds
            if timed:
                value += ' (' + schedule_range(req.departure_time, elapsed, elapsed+seconds,text) + ')'
                elapsed += seconds
        rows.append(f'<tr><td></td><td style="padding:4px 0 20px 8px">{line(value,dark)}</td></tr>')
    total = format_duration(elapsed / 60 if timed else req.total_minutes,text)
    schedule = schedule_range(req.departure_time,0,elapsed,text) if timed else c['schedule']
    total_walk = format_duration(walk_seconds / 60,text) if walk_known else '-'
    amount = f'₩{sum(prices):,.0f}' if prices else c['price_unknown']
    link = build_course_link(req)
    cta = f'<a href="{h(link)}" style="display:block;text-align:center;padding:16px;background:{primary};border-radius:10px;color:#fff;text-decoration:none;font-size:15px;font-weight:bold">{h(text["course_link"])}</a><p style="margin:10px 0 0;text-align:center;font-size:12px;color:{muted}">{h(c["reopen_hint"])}</p>' if link else ''
    estimated = req.return_estimated or any(s.routing_source == 'estimated' for s in req.stops)
    estimate = f'<p style="padding:12px;background:#fff7e9;border-radius:8px;font-size:12px;line-height:1.7;color:#775923">{h(text["walking_estimate_notice"])}</p>' if estimated else ''
    site = os.environ.get('PUBLIC_SITE_URL','https://busan-full-course.onrender.com').rstrip('/')
    date = req.departure_date.isoformat() if req.departure_date else ''
    departure = ' · '.join(filter(None,[req.start_label, text['departure'].format(time=req.departure_time) if req.departure_time else None]))
    if not departure:
        departure = c['start']
    return f'''<!doctype html><html lang="{h(req.language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{h(text['subject'])}</title></head>
<body style="margin:0;padding:0;background:#eff5f9;color:#203b50;font-family:Arial,'Malgun Gothic','Hiragino Sans',sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#eff5f9"><tr><td align="center" style="padding:16px 10px">
<table role="presentation" width="580" cellspacing="0" cellpadding="0" style="width:100%;max-width:580px;background:#fff;border-radius:18px;border:1px solid {border}">
<tr><td style="padding:28px 24px;background:{dark};border-radius:18px 18px 0 0;color:#fff"><p style="margin:0 0 12px;font-size:11px;letter-spacing:2px">BUSAN FULL COURSE</p><h1 style="margin:0;font-size:25px;line-height:1.5">{h(c['title'])}</h1>{f'<p style="margin:12px 0 0;font-size:12px">{h(date)}</p>' if date else ''}</td></tr>
<tr><td style="padding:22px 20px"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="table-layout:fixed"><tr>
<td style="padding:12px 8px;background:{pale};border-radius:10px;vertical-align:top"><p style="margin:0;font-size:11px;color:{muted}">{h(c['schedule'])}</p><p style="margin:8px 0;font-size:13px;font-weight:bold;line-height:1.6;overflow-wrap:anywhere">{h(schedule)}</p><p style="margin:0;font-size:11px;color:{muted}">{h(text['total'].format(n=total))}</p></td><td width="8"></td>
<td style="padding:12px 8px;background:{pale};border-radius:10px;vertical-align:top"><p style="margin:0;font-size:11px;color:{muted}">{h(c['places'])}</p><p style="margin:8px 0;font-size:16px;font-weight:bold">{len(req.stops)}</p><p style="margin:0;font-size:11px;color:{muted}">{h(c['walking'].format(time=total_walk))}</p></td><td width="8"></td>
<td style="padding:12px 8px;background:#f2f7fb;border-radius:10px;vertical-align:top"><p style="margin:0;font-size:11px;color:{muted}">{h(c['spend_title'])}</p><p style="margin:8px 0;font-size:14px;font-weight:bold;overflow-wrap:anywhere">{h(amount)}</p><p style="margin:0;font-size:11px;line-height:1.6;color:{muted}">{h(c['known_prices'])}</p></td>
</tr></table></td></tr>
<tr><td style="padding:13px 24px;background:{pale};font-size:12px;line-height:1.7;color:{dark}">{h(c['payment_notice'])}</td></tr>
<tr><td style="padding:24px 20px">{estimate}<p style="margin:0 0 20px;font-size:12px;line-height:1.7;color:{muted}">{h(departure)}</p><table role="presentation" width="100%" cellspacing="0" cellpadding="0">{''.join(rows)}</table><div style="padding:6px 0 8px">{cta}</div></td></tr>
<tr><td style="padding:22px 24px;background:#f5f9fc;border-radius:0 0 18px 18px"><p style="margin:0;font-size:11px;line-height:1.8;color:{muted}">{h(text['source'])}</p><p style="margin:12px 0 0;font-size:11px;color:{muted}">BUSAN FULL COURSE · <a href="{h(site)}" style="color:{primary}">{h(c['website'])}</a></p></td></tr>
</table></td></tr></table></body></html>'''