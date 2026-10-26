import unittest
from unittest.mock import patch, Mock
import requests
import pandas as pd
from app.services import walking
from app.services.route import next_places, recalculate_route, RouteConstraintError
from app.routers.notify import EmailRequest, build_email_body, EMAIL_COPY


class WalkingFallbackTests(unittest.TestCase):
    def setUp(self):
        self.key = patch.dict("os.environ", {"TMAP_APP_KEY":"test-only"}); self.key.start(); self.addCleanup(self.key.stop)
        self.cooldown = patch.object(walking,"_retry_after",0.0); self.cooldown.start(); self.addCleanup(self.cooldown.stop)
        self.clock = patch.object(walking,"monotonic",return_value=100); self.now=self.clock.start(); self.addCleanup(self.clock.stop)

    def response(self, status=200, headers=None):
        response=Mock(status_code=status, headers=headers or {})
        response.json.return_value={"features":[{"properties":{"totalTime":120,"totalDistance":150}},
            {"geometry":{"type":"LineString","coordinates":[[129.03,35.1],[129.031,35.101]]}}]}
        return response

    @patch.object(walking.requests,"post")
    def test_quota_pauses_calls_then_recovers_actual_routes(self, post):
        post.return_value=self.response(429)
        first=walking.walking_leg(35.1,129.03,35.101,129.031)
        self.assertEqual(first["routing_source"],"estimated"); self.assertEqual(first["leg_path"],[])
        self.assertGreater(first["leg_seconds"],0)
        walking.walking_leg(35.1,129.03,35.102,129.032)
        self.assertEqual(post.call_count,1)
        self.now.return_value=401; post.return_value=self.response()
        recovered=walking.walking_leg(35.1,129.03,35.101,129.031)
        self.assertEqual(recovered["routing_source"],"tmap")
        self.assertEqual(recovered["leg_seconds"],120); self.assertEqual(len(recovered["leg_path"]),2)
        self.assertEqual(post.call_count,2)

    @patch.object(walking.requests,"post")
    def test_transient_failures_fallback_but_auth_and_bad_requests_do_not(self, post):
        for failure in [requests.Timeout(), requests.ConnectionError(), self.response(503)]:
            walking._retry_after=0
            post.side_effect=failure if isinstance(failure,Exception) else None
            post.return_value=failure
            self.assertEqual(walking.walking_leg(35.1,129.03,35.101,129.031)["routing_source"],"estimated")
            self.assertEqual(walking._retry_after,130)
        post.side_effect=None
        for status in [400,401,403]:
            walking._retry_after=0; post.return_value=self.response(status)
            with self.assertRaises(walking.WalkingError): walking.walking_leg(35.1,129.03,35.101,129.031)

    @patch.object(walking.requests,"post")
    def test_retry_after_is_bounded_and_invalid_values_use_default(self,post):
        for header,expected in [('10',130),('999999',3700),('NaN',400),('nonsense',400)]:
            walking._retry_after=0; post.return_value=self.response(429,{'Retry-After':header})
            walking.walking_leg(35.1,129.03,35.101,129.031)
            self.assertEqual(walking._retry_after,expected)

    @patch.object(walking.requests,"post")
    def test_zero_length_and_missing_key(self,post):
        self.assertEqual(walking.walking_leg(35.1,129.03,35.1,129.03)["leg_seconds"],0)
        post.assert_not_called()
        with patch.dict('os.environ',{'TMAP_APP_KEY':''}):
            with self.assertRaises(walking.WalkingError): walking.walking_leg(35.1,129.03,35.101,129.031)

    @patch.object(walking.requests,"post")
    def test_fallback_keeps_candidates_selection_return_and_constraints(self,post):
        post.return_value=self.response(429)
        row=dict(id='fallback-test',name='테스트',address='부산 중구',category='식당',duration_min=30,
                 lat=35.101,lon=129.03,data_date='2026-10-26',place_type='merchant',payment_status='merchant_listed',source='test')
        with patch('app.services.route.rotate',side_effect=lambda rows:rows):
            result=next_places(pd.DataFrame([row]),35.1,129.03,[],'식당',90,True)
        self.assertTrue(result['routing_estimated'])
        selected=result['alternatives'][0]
        course=recalculate_route(35.1,129.03,[selected],90,True)
        self.assertTrue(course['routing_estimated']); self.assertEqual(course['routing_source'],'estimated')
        self.assertEqual(course['return_leg']['routing_source'],'estimated')
        self.assertAlmostEqual(course['total_seconds'],1800+2*selected['leg_seconds'])
        with self.assertRaises(RouteConstraintError): recalculate_route(35.1,129.03,[{**row,'lat':35.15}],90)
        with self.assertRaises(RouteConstraintError): recalculate_route(35.1,129.03,[{**row,'duration_min':41}],30)
        self.assertEqual(post.call_count,1)

    def test_estimate_warning_in_all_email_languages_including_return_only(self):
        for lang in EMAIL_COPY:
            for source,back in [('estimated',False),('tmap',True),('tmap',False)]:
                req=EmailRequest(email='test@example.com',language=lang,return_estimated=back,
                    stops=[dict(order=1,name='테스트',address='부산',category='식당',routing_source=source)])
                body=build_email_body(req)
                self.assertEqual(EMAIL_COPY[lang]['walking_estimate_notice'] in body,source=='estimated' or back)


if __name__=='__main__': unittest.main()
