import unittest
import os
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
from pydantic import ValidationError
from app.routers.notify import EmailRequest, build_email_body, build_course_link, send_route_email, EMAIL_COPY

class ScheduleEmailTests(unittest.TestCase):
    def request(self, **changes):
        values=dict(email='test@example.com',departure_time='10:00',total_minutes=110,
            start_lat=35.1,start_lon=129.03,return_to_start=True,return_minutes=5,
            stops=[dict(id='test-1',order=1,name='테스트 식당',category='식당',address='부산 중구',leg_minutes=5,duration_min=60),
                   dict(id='test-2',order=2,name='테스트 카페',category='카페/디저트',address='부산 중구',leg_minutes=10,duration_min=30)])
        values.update(changes)
        return EmailRequest(**values)

    def test_schedule_and_reopen_link_preserve_departure(self):
        req=self.request();body=build_email_body(req)
        for value in ['10:00 ~ 10:05','테스트 식당 (10:05 ~ 11:05)','11:05 ~ 11:15','테스트 카페 (11:15 ~ 11:45)','11:45 ~ 11:50','약 1시간 50분']:
            self.assertIn(value,body)
        self.assertEqual(parse_qs(urlparse(build_course_link(req)).query)['depart'],['10:00'])

    def test_seconds_and_next_day_in_every_language(self):
        for language,text in EMAIL_COPY.items():
            req=self.request(language=language,departure_time='23:58',return_to_start=False)
            req.stops[0].leg_seconds=61
            req.stops[1].leg_seconds=61
            req.stops[1].duration_min=0
            body=build_email_body(req)
            self.assertIn('23:58 ~ '+text['next_day'].format(time='00:00'),body)
            self.assertIn(text['next_day'].format(time='01:00')+' ~ '+text['next_day'].format(time='01:01'),body)

    def test_legacy_requests_and_missing_durations_do_not_invent_times(self):
        req=self.request(departure_time=None)
        self.assertNotIn(' ~ ',build_email_body(req))
        self.assertNotIn('depart=',build_course_link(req))
        req=self.request();req.stops[0].duration_min=None
        self.assertNotIn(' ~ ',build_email_body(req))

    def test_delivery_keeps_schedule_in_each_language_without_sending_mail(self):
        with patch.dict(os.environ, {'EMAIL_DELIVERY_ENABLED':'true', 'BREVO_API_KEY':'test-key', 'EMAIL_FROM':'sender@example.com'}), patch('app.routers.notify.requests.post') as post:
            post.return_value.json.return_value={'messageId':'mock-message'}
            for language in EMAIL_COPY:
                req=self.request(language=language,email_consent=True)
                expected=build_email_body(req)
                self.assertTrue(send_route_email(req)['sent'])
                self.assertEqual(post.call_args.kwargs['json']['textContent'],expected)
                self.assertIn('10:05 ~ 11:05',expected)

    def test_invalid_clock_and_nonfinite_durations_are_rejected(self):
        for value in ['24:00','9:00','10:60','10:00\n']:
            with self.assertRaises(ValidationError): self.request(departure_time=value)
        for value in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValidationError): self.request(return_minutes=value)

if __name__=='__main__':unittest.main()
