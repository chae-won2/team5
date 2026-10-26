import unittest
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from app.main import app
from app.services.walking import walking_leg, WalkingError
from app.data_loader import load_places


class WalkingTests(unittest.TestCase):
    @patch("app.services.walking.requests.post")
    def test_summary_seconds_and_geometry(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {"features": [
            {"properties": {"totalTime": 125, "totalDistance": 150}},
            {"geometry": {"type": "LineString", "coordinates": [[129, 35], [129.1, 35.1]]}}]}
        result = walking_leg(35, 129, 35.1, 129.1)
        self.assertEqual(result["leg_minutes"], 2.1)
        self.assertEqual(result["leg_path"][0], [35, 129])
        self.assertNotIn("appKey", post.call_args.kwargs["params"])

    @patch("app.services.walking.requests.post")
    def test_auth_failure_does_not_leak_response(self, post):
        post.return_value = Mock(status_code=403, text="private upstream data")
        with self.assertRaises(WalkingError) as exc:
            walking_leg(35, 129, 35.1, 129.1)
        self.assertNotIn("private upstream data", str(exc.exception))

    @patch("app.services.route.walking_leg")
    def test_recommend_and_swap_include_stay_and_start_leg(self, leg):
        leg.return_value = {"leg_minutes": 10, "leg_distance_m": 500, "leg_path": []}
        client = TestClient(app)
        response = client.post("/api/recommend", json={"start_lat":35.1,"start_lon":129.03,
            "categories":["식당"],"max_minutes":180})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_walk_minutes"], 10 * len(data["stops"]))
        self.assertEqual(data["total_minutes"], data["total_walk_minutes"] + sum(s["duration_min"] for s in data["stops"]))
        self.assertFalse(data["over_budget"])
        self.assertLessEqual(data["total_minutes"], 180)
        ids = [s["id"] for s in data["stops"]]
        ids[0] = data["alternatives"][0]["id"]
        swap = client.post("/api/recommend/recalculate", json={"start_lat":35.1,
            "start_lon":129.03,"stop_ids":ids,"max_minutes":360})
        self.assertEqual(swap.status_code, 200)
        self.assertEqual(swap.json()["stops"][0]["id"], ids[0])
        self.assertEqual(swap.json()["total_walk_minutes"], 10 * len(ids))
        self.assertEqual(client.post("/api/recommend/recalculate", json={"start_lat":35.1,
            "start_lon":129.03,"stop_ids":["unknown"]}).status_code, 422)

    def test_catalog_durations(self):
        catalog = load_places()
        self.assertTrue(catalog.duration_min.gt(0).all())
        self.assertTrue(catalog.loc[catalog.place_type.eq("market"), "duration_min"].eq(60).all())

    @patch("app.services.route.walking_leg")
    def test_mvp_tourism_and_catalog_only(self, leg):
        leg.return_value = {"leg_minutes": 5, "leg_distance_m": 300, "leg_path": []}
        client = TestClient(app)
        catalog = load_places()
        allowed = set(catalog.id)
        response = client.post("/api/recommend", json={"start_lat":35.1,"start_lon":129.03,
            "categories":["관광명소"],"max_minutes":180})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(len(data["stops"]), 0)
        self.assertLessEqual(data["total_minutes"], 180)
        self.assertTrue(all(s["category"] == "관광명소" for s in data["stops"]))
        self.assertTrue(all(s["id"] in allowed for s in data["stops"] + data["alternatives"]))
        self.assertEqual(len(client.get("/api/spots").json()), len(catalog[catalog.category.eq("관광명소")]))
        self.assertEqual(client.get("/api/spots/categories").json(), ["식당", "카페/디저트", "관광명소", "쇼핑"])
        legacy = client.post("/api/recommend/recalculate", json={"start_lat":35.1,
            "start_lon":129.03,"stop_ids":["legacy-only-id"]})
        self.assertEqual(legacy.status_code, 422)

    def test_email_requires_consent_without_sending(self):
        client = TestClient(app)
        body = {"email": "test@example.com", "stops": []}
        self.assertEqual(client.post("/api/notify/email", json=body).status_code, 400)
        with patch("app.routers.notify.GMAIL_ADDRESS", None):
            response = client.post("/api/notify/email", json={**body, "email_consent": True})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["sent"])

    @patch("app.services.route.walking_leg")
    def test_time_budget_uses_actual_walk_and_stay(self, leg):
        from app.services.route import recommend_route
        import pandas as pd
        base = load_places().iloc[0].to_dict()
        catalog = pd.DataFrame([{**base, "id": str(i), "lat": 35.1 + i * .001,
                                 "lon":129.03, "duration_min":30, "category":"관광명소"} for i in range(1, 9)])
        leg.return_value = {"leg_minutes": 15, "leg_distance_m": 500, "leg_path": []}
        short = recommend_route(catalog, 35.1,129.03,max_minutes=30)
        self.assertEqual(short["stops"], [])
        self.assertEqual(short["total_minutes"], 0)
        medium = recommend_route(catalog,35.1,129.03,max_minutes=90)
        self.assertEqual(len(medium["stops"]), 2)
        self.assertEqual(medium["total_minutes"],90)
        long = recommend_route(catalog,35.1,129.03,max_minutes=360)
        self.assertEqual(len(long["stops"]),8)
        self.assertEqual(long["total_minutes"],360)

    @patch("app.services.route.walking_leg")
    def test_shopping_and_over_budget_swap(self, leg):
        leg.return_value = {"leg_minutes": 20, "leg_distance_m":500, "leg_path":[]}
        c = TestClient(app)
        body = {"start_lat":35.1,"start_lon":129.03}
        self.assertEqual(c.post("/api/recommend",json={**body,"max_minutes":361}).status_code,422)
        self.assertEqual(c.post("/api/recommend",json={**body,"max_minutes":29}).status_code,422)
        self.assertEqual(c.post("/api/recommend",json={**body,"categories":["unknown"]}).status_code,422)
        shopping = c.post("/api/recommend",json={**body,"categories":["쇼핑"],"max_minutes":360})
        self.assertEqual(shopping.status_code,200)
        self.assertGreaterEqual(sum(stop["category"] == "쇼핑" for stop in shopping.json()["stops"]), 1)
        self.assertEqual(next(stop["duration_min"] for stop in shopping.json()["stops"] if stop["category"] == "쇼핑"), 25)
        place = load_places().query("duration_min >= 60").iloc[0]
        swap = c.post("/api/recommend/recalculate",json={**body,"stop_ids":[place.id],"max_minutes":30})
        self.assertEqual(swap.status_code,422)
        cafe = c.post("/api/recommend",json={**body,"categories":["카페/디저트"],"selected_only":True,"max_minutes":90})
        self.assertEqual(cafe.status_code,200)
        self.assertTrue(cafe.json()["stops"])
        self.assertTrue(all(s["category"] == "카페/디저트" for s in cafe.json()["stops"]))

    @patch("app.services.route.walking_leg")
    def test_origin_twenty_minute_limit_and_swap(self, leg):
        from app.services.route import recommend_route, recalculate_route, RouteConstraintError
        import pandas as pd
        base = load_places().iloc[0].to_dict()
        place = {**base, "id":"outside", "lat":35.11,"lon":129.03,"duration_min":30,"category":"관광명소"}
        leg.return_value = {"leg_minutes":20.0,"leg_seconds":1201,"leg_distance_m":1500,"leg_path":[]}
        result = recommend_route(pd.DataFrame([place]),35.1,129.03,max_minutes=180)
        self.assertFalse(result["stops"])
        self.assertFalse(result["alternatives"])
        with self.assertRaises(RouteConstraintError):
            recalculate_route(35.1,129.03,[place],180)
        leg.return_value = {"leg_minutes":20,"leg_seconds":1200,"leg_distance_m":1500,"leg_path":[]}
        result = recommend_route(pd.DataFrame([place]),35.1,129.03,max_minutes=180)
        self.assertEqual(len(result["stops"]),1)
        self.assertEqual(result["stops"][0]["origin_walk_minutes"],20)

    @patch("app.services.route.walking_leg")
    def test_return_leg_reserved_and_included(self, leg):
        from app.services.route import recommend_route, recalculate_route
        import pandas as pd
        base = load_places().iloc[0].to_dict()
        rows = [{**base,"id":str(i),"lat":35.1+i*.001,"lon":129.03,"duration_min":30,"category":"관광명소"} for i in range(1,5)]
        leg.return_value = {"leg_minutes":10,"leg_distance_m":500,"leg_path":[[35.1,129.03]]}
        result = recommend_route(pd.DataFrame(rows),35.1,129.03,max_minutes=90,return_to_start=True)
        self.assertEqual(len(result["stops"]),2)
        self.assertEqual(result["total_minutes"],90)
        self.assertEqual(result["total_walk_minutes"],30)
        self.assertEqual(result["return_leg"]["leg_minutes"],10)
        swapped = recalculate_route(35.1,129.03,result["stops"],90,True)
        self.assertEqual(swapped["total_minutes"],90)

    @patch("app.services.route.walking_leg")
    def test_preferences_and_cross_category_alternatives(self, leg):
        from app.services.route import recommend_route
        import pandas as pd
        base = load_places().iloc[0].to_dict()
        rows=[]
        for i,category in enumerate(["식당","카페·디저트","관광명소","쇼핑"]):
            for j in range(3):
                rows.append({**base,"id":f"{i}:{j}","lat":35.1+(i*3+j+1)*.001,
                             "lon":129.03,"duration_min":30,"category":category})
        leg.return_value={"leg_minutes":5,"leg_distance_m":300,"leg_path":[]}
        catalog=pd.DataFrame(rows)
        result=recommend_route(catalog,35.1,129.03,categories=["식당"],max_minutes=180)
        self.assertEqual(result["stops"][0]["category"],"식당")
        self.assertGreater(sum(p["category"]=="식당" for p in result["stops"]),1)
        self.assertTrue(any(p["category"]=="관광명소" for p in result["stops"]))
        self.assertFalse(any(p["category"] in ["카페/디저트","쇼핑"] for p in result["stops"]))
        strict=recommend_route(catalog,35.1,129.03,categories=["식당"],max_minutes=180,selected_only=True)
        self.assertEqual(len(strict["stops"]),1)
        self.assertEqual({p["category"] for p in strict["alternatives"]},{"식당","카페/디저트","관광명소","쇼핑"})
        self.assertTrue(all(p["origin_walk_minutes"]<=20 for p in strict["alternatives"]))

    def test_roundtrip_email_return_time(self):
        from app.routers.notify import EmailRequest,build_email_body
        req=EmailRequest(email="test@example.com",start_lat=35.1,start_lon=129.03,return_to_start=True,return_minutes=8,
            stops=[{"order":1,"name":"test","category":"관광명소","address":"test","lat":35.11,"lon":129.04}])
        self.assertIn("8분",build_email_body(req))

    def test_taste_tags_require_exact_district_and_unique_name(self):
        import pandas as pd
        import tempfile
        from pathlib import Path
        from app.services.place_tags import busan_taste_matches
        frame=pd.DataFrame([
            {"id":"a","name":"셰프 곤","address":"부산 중구 중구로 12","category":"식당"},
            {"id":"b","name":"셰프 곤 별관","address":"부산 중구 중구로 13","category":"식당"},
            {"id":"c","name":"셰프 곤","address":"부산 서구 서구로 1","category":"식당"}])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"taste.csv"
            path.write_text("구군,식당명,영문명\n중구,셰프곤,Chef Gon\n",encoding="utf-8-sig")
            self.assertEqual(busan_taste_matches(frame,path),{"a":"셰프곤"})
            duplicate=pd.concat([frame,pd.DataFrame([{"id":"d","name":"셰프곤","address":"부산 중구 다른길 1","category":"식당"}])])
            self.assertEqual(busan_taste_matches(duplicate,path),{})

    def test_four_language_email_and_consent(self):
        from app.routers.notify import EmailRequest, build_email_body, EMAIL_COPY
        client=TestClient(app)
        body={"email":"test@example.com","stops":[{"order":1,"name":"용두산공원","category":"관광명소","address":"부산 중구 용두산길", "leg_minutes":10,"duration_min":30}],"total_minutes":40}
        for language in ["ko","en","ja","zh-TW"]:
            req=EmailRequest(**body,language=language)
            text=build_email_body(req)
            self.assertIn("용두산공원",text)
            self.assertIn("부산 중구 용두산길",text)
            self.assertIn(EMAIL_COPY[language]["categories"]["관광명소"],text)
            denied=client.post("/api/notify/email",json={**body,"language":language})
            self.assertEqual(denied.status_code,400)
            self.assertEqual(denied.json()["detail"],EMAIL_COPY[language]["consent"])
            with patch("app.routers.notify.GMAIL_ADDRESS",None):
                pending=client.post("/api/notify/email",json={**body,"language":language,"email_consent":True})
            self.assertEqual(pending.status_code,200)
            self.assertFalse(pending.json()["sent"])
        self.assertEqual(client.post("/api/notify/email",json={**body,"language":"zh-CN"}).status_code,422)

    def test_official_email_labels_and_korean_fallback(self):
        from app.routers.notify import EmailRequest, build_email_body, EMAIL_COPY, send_route_email
        from app.services.place_labels import LABELS
        entry = next(row for row in LABELS if "en" in row["translations"])
        stop = {"id": entry["id"], "order": 1, "name": entry["name_ko"], "address": entry["address_ko"], "category": "관광명소"}
        for language in ["en", "ja", "zh-TW"]:
            req = EmailRequest(email="test@example.com", email_consent=True, language=language,
                stops=[stop, {**stop, "id": "unknown", "name": "미확인 가게"}])
            body = build_email_body(req)
            self.assertIn(entry["name_ko"], body)
            self.assertIn("미확인 가게", body)
            self.assertIn(EMAIL_COPY[language]["official_fallback"], body)
            if language in entry["translations"]:
                self.assertIn(entry["translations"][language]["name"], body)
            with patch("app.routers.notify.smtplib.SMTP_SSL") as smtp, patch("app.routers.notify.GMAIL_ADDRESS", "sender@example.com"), patch("app.routers.notify.GMAIL_APP_PASSWORD", "test"):
                self.assertTrue(send_route_email(req)["sent"])
                smtp.return_value.__enter__.return_value.sendmail.assert_called_once()
        invalid = EmailRequest(email="test@example.com", language="en", stops=[{**stop, "id": "different"}])
        self.assertNotIn(entry["translations"]["en"]["name"], build_email_body(invalid))


if __name__ == "__main__":
    unittest.main()
