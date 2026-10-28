import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
import pandas as pd
from app.routers.notify import EmailRequest, build_email_html, build_course_link, send_route_email, EMAIL_COPY

class EmailCardTests(unittest.TestCase):
    def req(self, **changes):
        values=dict(email='test@example.com',email_consent=True,departure_date='2026-10-28',departure_time='10:00',start_lat=35.1,start_lon=129.03,start_label='남포역',return_to_start=True,return_seconds=61,stops=[dict(id='one',order=1,name='식당 <테스트>',address='부산 중구',category='식당',leg_seconds=61,duration_min=60),dict(id='two',order=2,name='카페',address='부산 중구',category='카페·디저트',leg_seconds=61,duration_min=30)])
        values.update(changes)
        return EmailRequest(**values)

    def catalog(self):
        return pd.DataFrame([dict(id='one',name='식당 <테스트>',address='부산 중구',estimated_spend=12000,payment_status='merchant_listed'),dict(id='two',name='카페',address='부산 중구',estimated_spend=None,payment_status='not_verified')])

    @patch('app.services.email_cards.load_places')
    def test_timeline_prices_payment_links_and_escape_in_four_languages(self,load):
        load.return_value=self.catalog()
        for lang in EMAIL_COPY:
            req=self.req(language=lang); html=build_email_html(req); c=EMAIL_COPY[lang]['card']
            for expected in ['#176b9c','10:02 ~ 11:02','11:03 ~ 11:33','11:33 ~ 11:34','₩12,000','식당 &lt;테스트&gt;','2026-10-28',c['known_prices'],c['payment_listed'],c['payment_check'],'https://www.google.com/maps/dir/?api=1','html lang="'+lang+'"']:
                self.assertIn(expected,html)
            self.assertNotIn('<테스트>',html)
            self.assertNotIn('nan',html)
            self.assertEqual(parse_qs(urlparse(build_course_link(req)).query)['date'],['2026-10-28'])

    @patch('app.services.email_cards.load_places')
    def test_missing_schedule_prices_and_identity_mismatch_stay_unknown(self,load):
        load.return_value=self.catalog()
        req=self.req(departure_time=None,return_to_start=False);req.stops[0].name='다른 가게'
        html=build_email_html(req)
        self.assertNotIn('₩12,000',html);self.assertNotIn(' ~ ',html)
        self.assertIn(EMAIL_COPY['ko']['card']['price_unknown'],html)
        self.assertNotIn(EMAIL_COPY['ko']['card']['payment_listed'],html)

    @patch('app.services.email_cards.load_places')
    def test_estimates_midnight_empty_and_conditional_fees(self,load):
        load.return_value=self.catalog()
        req=self.req(departure_time='23:59',return_estimated=True); html=build_email_html(req)
        self.assertIn('익일',html);self.assertIn(EMAIL_COPY['ko']['walking_estimate_notice'],html)
        self.assertNotIn('nan',build_email_html(self.req(stops=[])))
        for status in ['free','paid','conditional','unknown']:
            load.return_value=pd.DataFrame([dict(id='spot',name='명소',address='부산 중구',admission_fee_status=status,admission_fee_krw=10000,payment_status='not_accepted')])
            req=self.req(stops=[dict(id='spot',order=1,name='명소',address='부산 중구',category='관광명소',leg_seconds=60,duration_min=30)])
            html=build_email_html(req)
            self.assertEqual('일반 성인 입장료 약 ₩10,000' in html,status=='paid')
            self.assertEqual('입장료 무료' in html,status=='free')
            self.assertIn('동백전 결제 불가',html)

    @patch('app.services.email_cards.load_places')
    @patch('app.routers.notify.requests.post')
    def test_brevo_sends_html_and_plain_alternatives(self,post,load):
        load.return_value=self.catalog();post.return_value.json.return_value={'messageId':'fake'}
        with patch.dict('os.environ',{'BREVO_API_KEY':'test','EMAIL_FROM':'sender@example.com','EMAIL_DELIVERY_ENABLED':'true'}):
            self.assertTrue(send_route_email(self.req())['sent'])
        payload=post.call_args.kwargs['json'];self.assertIn('<table',payload['htmlContent']);self.assertIn('10:00',payload['textContent'])

    @patch('app.services.email_cards.load_places')
    @patch('app.routers.notify.smtplib.SMTP_SSL')
    def test_smtp_uses_multipart_alternative(self,smtp,load):
        from email import message_from_string
        load.return_value=self.catalog()
        with patch.dict('os.environ',{'BREVO_API_KEY':'','EMAIL_DELIVERY_ENABLED':'true'}),patch('app.routers.notify.GMAIL_ADDRESS','sender@example.com'),patch('app.routers.notify.GMAIL_APP_PASSWORD','fake'):
            self.assertTrue(send_route_email(self.req())['sent'])
        msg=message_from_string(smtp.return_value.__enter__.return_value.sendmail.call_args.args[2]);self.assertEqual(msg.get_content_type(),'multipart/alternative');self.assertEqual([p.get_content_type() for p in msg.get_payload()],['text/plain','text/html'])

if __name__=='__main__':unittest.main()