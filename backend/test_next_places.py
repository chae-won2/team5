import unittest
from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app
from app.data_loader import load_places
from app.services.route import next_places

class NextPlaceTests(unittest.TestCase):
    def setUp(self):
        base = load_places().iloc[0].to_dict()
        self.rows = [{**base, "id": "a", "category": "관광명소", "duration_min":30, "lat":35.101, "lon":129.03},
                     {**base, "id": "b", "category": "카페·디저트", "duration_min":45, "lat":35.102, "lon":129.03},
                     {**base, "id": "c", "category": "식당", "duration_min":60, "lat":35.103, "lon":129.03}]
        self.catalog = pd.DataFrame(self.rows)

    @patch("app.services.route.walking_leg")
    @patch("app.services.route.rotate", side_effect=lambda places: places)
    def test_prices_survive_candidates_and_selected_stops_without_affecting_order(self, rotate, walk):
        walk.return_value = {"leg_minutes":5,"leg_seconds":300,"leg_path":[],"leg_distance_m":300}
        rows = [{**self.rows[0], "estimated_spend":None}, {**self.rows[1], "estimated_spend":12000}]
        catalog = pd.DataFrame(rows)
        result = next_places(catalog,35.1,129.03,[],"카페/디저트",180)
        self.assertEqual(result["alternatives"][0]["estimated_spend"],12000)
        import json
        from fastapi.encoders import jsonable_encoder
        from app.routers.recommend import recalculate, RecalculateRequest
        with patch("app.routers.recommend.load_places", return_value=catalog):
            response = recalculate(RecalculateRequest(start_lat=35.1,start_lon=129.03,
                stop_ids=[rows[0]["id"],rows[1]["id"]],max_minutes=180))
        payload = json.loads(json.dumps(jsonable_encoder(response), allow_nan=False))
        self.assertEqual([p["estimated_spend"] for p in payload["stops"]],[None,12000])

    @patch("app.services.route.walking_leg")
    def test_preserves_chosen_order_and_uses_last_location(self, walk):
        walk.return_value = {"leg_minutes":5,"leg_seconds":300,"leg_path":[],"leg_distance_m":300}
        result = next_places(self.catalog,35.1,129.03,self.rows[:1],"카페/디저트",180)
        self.assertEqual([p["id"] for p in result["stops"]],["a"])
        self.assertEqual([p["id"] for p in result["alternatives"]],["b"])
        self.assertEqual(result["alternatives"][0]["projected_total_minutes"],85)
        self.assertIn(((35.101,129.03,35.102,129.03),),[(c.args,) for c in walk.call_args_list])
        result = next_places(self.catalog,35.1,129.03,[self.rows[2],self.rows[0]],None,180)
        self.assertEqual([s["id"] for s in result["stops"]],["c","a"])
        self.assertEqual([s["order"] for s in result["stops"]],[1,2])

    @patch("app.services.route.walking_leg")
    def test_budget_return_and_no_unselected_candidates(self, walk):
        walk.return_value={"leg_minutes":5,"leg_seconds":300,"leg_path":[],"leg_distance_m":300}
        result=next_places(self.catalog,35.1,129.03,self.rows[:1],"카페/디저트",85,True)
        self.assertEqual(len(result["alternatives"]),1)
        self.assertTrue(result["alternatives"][0]["over_budget"])
        self.assertEqual(result["alternatives"][0]["projected_total_minutes"],90)
        self.assertEqual(result["remaining_minutes"],45)
        self.assertEqual(next_places(self.catalog,35.1,129.03,[self.rows[1]],"카페/디저트",180)["alternatives"],[])
        self.assertFalse(next_places(self.catalog,35.1,129.03,[self.rows[0]],"관광명소",180)["alternatives"])

    @patch("app.services.route.walking_leg")
    def test_repeated_categories_can_be_suggested_selected_and_reopened(self, walk):
        walk.return_value = {"leg_minutes":5,"leg_seconds":300,"leg_path":[],"leg_distance_m":300}
        for category in ["식당", "카페·디저트", "쇼핑"]:
            with self.subTest(category=category):
                rows = [{**self.rows[0], "id":str(i), "category":category, "lat":35.101+i*.001} for i in range(3)]
                catalog = pd.DataFrame(rows)
                result = next_places(catalog,35.1,129.03,rows[:2],category,100)
                self.assertEqual([p["id"] for p in result["alternatives"]],["2"])
                with patch("app.routers.recommend.load_places", return_value=catalog):
                    for endpoint in ["/api/recommend/next", "/api/recommend/recalculate"]:
                        response = TestClient(app).post(endpoint,json={"start_lat":35.1,"start_lon":129.03,"stop_ids":["0","1","2"],"max_minutes":100})
                        self.assertEqual(response.status_code,200)
                        self.assertEqual(len(response.json()["stops"]),3)
                        self.assertTrue(response.json()["over_budget"])

    @patch("app.services.route.walking_leg")
    def test_origin_limit_and_empty_selection(self, walk):
        walk.return_value={"leg_minutes":20,"leg_seconds":1201,"leg_path":[],"leg_distance_m":1500}
        self.assertFalse(next_places(self.catalog,35.1,129.03,[],"식당",180)["alternatives"])
        result=next_places(self.catalog,35.1,129.03,[],None,180,True)
        self.assertEqual(result["stops"],[])
        self.assertEqual(result["total_minutes"],0)
        self.assertIsNone(result["return_leg"])

    @patch("app.services.route.walking_leg")
    @patch("app.services.route.status_at")
    def test_confirmed_closed_places_are_excluded_but_unknown_and_open_stay(self, status_at, walk):
        walk.return_value = {"leg_minutes": 5, "leg_seconds": 300, "leg_path": [], "leg_distance_m": 300}
        status_at.side_effect = lambda place_id, weekday, minutes: {"b": "closed"}.get(place_id, "unknown")
        # "b" is the only 카페·디저트 candidate; confirmed-closed means no alternatives at all.
        result = next_places(self.catalog, 35.1, 129.03, [], "카페/디저트", 180, opening=(0, 600))
        self.assertEqual(result["alternatives"], [])

        from app.services.route import recommend_route
        result = recommend_route(self.catalog, 35.1, 129.03, opening=(0, 600))
        chosen_and_alt_ids = {s["id"] for s in result["stops"]} | {a["id"] for a in result["alternatives"]}
        self.assertNotIn("b", chosen_and_alt_ids)
        self.assertIn("a", chosen_and_alt_ids)  # unknown status is never excluded

    @patch("app.services.route.walking_leg")
    def test_opening_status_is_unknown_without_departure_context(self, walk):
        walk.return_value = {"leg_minutes": 5, "leg_seconds": 300, "leg_path": [], "leg_distance_m": 300}
        result = next_places(self.catalog, 35.1, 129.03, [], "카페/디저트", 180)
        self.assertEqual(result["alternatives"][0]["opening_status"], "unknown")

    def test_invalid_ids_and_category_rejected(self):
        client=TestClient(app); base={"start_lat":35.1,"start_lon":129.03}
        for change in [{"stop_ids":["missing"]},{"stop_ids":["same","same"]},{"category":"unknown"}]:
            self.assertEqual(client.post("/api/recommend/next",json={**base,**change}).status_code,422)
        self.assertEqual(client.post("/api/recommend/next",json=base).status_code,200)

    @patch('app.services.route.walking_leg')
    def test_56_minutes_remaining_allows_60_minute_cafe_and_shared_course(self, walk):
        walk.return_value={'leg_minutes':5,'leg_seconds':300,'leg_path':[],'leg_distance_m':300}
        fixed={**self.rows[0], 'duration_min':299}
        cafe={**self.rows[1], 'duration_min':60}
        catalog=pd.DataFrame([fixed,cafe])
        result=next_places(catalog,35.1,129.03,[fixed],'카페/디저트',360)
        self.assertEqual(result['remaining_minutes'],56)
        self.assertTrue(result['alternatives'][0]['over_budget'])
        self.assertEqual(result['alternatives'][0]['projected_total_minutes'],369)
        selected=next_places(catalog,35.1,129.03,[fixed,cafe],None,360)
        self.assertEqual([p['id'] for p in selected['stops']],['a','b'])
        self.assertTrue(selected['over_budget'])
        self.assertEqual(selected['total_minutes'],369)
        self.assertEqual(next_places(catalog,35.1,129.03,[fixed],None,360)['total_minutes'],304)
        with patch('app.routers.recommend.load_places',return_value=catalog):
            for endpoint in ['/api/recommend/next','/api/recommend/recalculate']:
                response=TestClient(app).post(endpoint,json={'start_lat':35.1,'start_lon':129.03,'stop_ids':['a','b'],'max_minutes':360,'return_to_start':True})
                self.assertEqual(response.status_code,422)

    @patch("app.services.route.walking_leg")
    def test_previous_stop_radius_and_exact_overrun_boundary(self, walk):
        from app.services.route import recalculate_route, RouteConstraintError
        first = {**self.rows[0], "duration_min":10}
        second = {**self.rows[1], "duration_min":10}
        def segment(a,b,c,d):
            seconds = 1800 if (a,c) == (35.1,second["lat"]) else 1200
            return {"leg_minutes":seconds/60,"leg_seconds":seconds,"leg_path":[],"leg_distance_m":500}
        walk.side_effect = segment
        # Second stop is 30 minutes from the origin but only 20 from the first stop.
        result = next_places(pd.DataFrame([first,second]),35.1,129.03,[first],"카페/디저트",60)
        self.assertEqual([p["id"] for p in result["alternatives"]],["b"])
        self.assertEqual(recalculate_route(35.1,129.03,[first,second],60)["total_minutes"],60)
        self.assertNotIn((35.1,129.03,second["lat"],second["lon"]), [c.args for c in walk.call_args_list])
        walk.side_effect = None
        fixed = {**first, "duration_min":40}
        candidate = {**second, "duration_min":20}
        catalog = pd.DataFrame([fixed,candidate])
        for seconds, allowed in [(300,True),(301,False)]:
            with self.subTest(seconds=seconds):
                walk.return_value = {"leg_minutes":round(seconds/60,1),"leg_seconds":seconds,"leg_path":[],"leg_distance_m":300}
                result = next_places(catalog,35.1,129.03,[fixed],"카페/디저트",60)
                self.assertEqual(bool(result["alternatives"]),allowed)
                if allowed:
                    self.assertTrue(result["alternatives"][0]["over_budget"])
                    self.assertEqual(result["alternatives"][0]["projected_total_minutes"],70)
                    self.assertEqual(recalculate_route(35.1,129.03,[fixed,candidate],60)["total_minutes"],70)
                else:
                    with self.assertRaises(RouteConstraintError):
                        recalculate_route(35.1,129.03,[fixed,candidate],60)
        walk.return_value = {"leg_minutes":20,"leg_seconds":1201,"leg_path":[],"leg_distance_m":1500}
        with self.assertRaises(RouteConstraintError):
            recalculate_route(35.1,129.03,[first],180)

if __name__ == "__main__":unittest.main()
