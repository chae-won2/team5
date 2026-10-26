import unittest
from unicodedata import normalize
from unittest.mock import patch

from app.services.place_labels import romanized_name, LABELS
from app.services.route import _place_fields, next_places
from app.routers.notify import EmailRequest, build_email_body, EMAIL_COPY
import pandas as pd


class RomanizedNamesTests(unittest.TestCase):
    def row(self, **changes):
        return dict(id="merchant-test", name="대양상회", address="부산 중구 테스트로 1",
                    category="식당", duration_min=60, lon=129.03, lat=35.1,
                    data_date="2026-10-26", place_type="merchant",
                    payment_status="merchant_listed", source="test", **changes)

    def test_mixed_names_preserve_existing_latin_digits_and_punctuation(self):
        self.assertEqual(romanized_name("BNK부산은행 갤러리 2호점"), "BNKBusaneunhaeng Gaelleori 2Hojeom")
        self.assertEqual(romanized_name("비바로카페(VIVARO)"), "Bibarokape(VIVARO)")
        self.assertEqual(romanized_name("CAFE 123"), "")
        self.assertEqual(romanized_name(""), "")
        self.assertEqual(romanized_name(normalize("NFD", "대양상회")), "Daeyangsanghoe")

    def test_api_fields_separate_official_and_automatic_names_without_replacing_korean(self):
        row = self.row()
        for lang in ("ko", "en", "ja", "zh-TW"):
            result = _place_fields(row, language=lang)
            self.assertEqual(result["name"], "대양상회")
            self.assertEqual(result["official_name"], "")
            self.assertEqual(result["official_names"], {})
            self.assertEqual(result["romanized_name"], "Daeyangsanghoe")
        official = next(p for p in LABELS if p["translations"].get("en", {}).get("name"))
        result = _place_fields({**row, "id":official["id"], "name":official["name_ko"],
                                "address":official["address_ko"]}, language="en")
        self.assertEqual(result["official_name"], official["translations"]["en"]["name"])
        self.assertEqual(result["official_names"]["en"], result["official_name"])

    @patch("app.services.route.rotate", side_effect=lambda rows: rows)
    @patch("app.services.route.walking_leg", return_value={"leg_minutes":5,"leg_seconds":300,"leg_path":[],"leg_distance_m":300})
    def test_candidates_and_fixed_stops_both_have_reading_aids(self, walk, rotate):
        row = self.row()
        catalog = pd.DataFrame([row])
        candidate = next_places(catalog,35.1,129.03,[],"식당",180,language="en")["alternatives"][0]
        from app.routers.recommend import recommend_next, NextPlaceRequest
        with patch("app.routers.recommend.load_places", return_value=catalog):
            chosen = recommend_next(NextPlaceRequest(start_lat=35.1,start_lon=129.03,
                stop_ids=[row["id"]],max_minutes=180,language="ja"))["stops"][0]
        self.assertEqual(candidate["romanized_name"], chosen["romanized_name"])
        self.assertEqual(candidate["name"], "대양상회")

    def test_mail_uses_server_generated_reading_aid_for_each_foreign_language(self):
        for lang in EMAIL_COPY:
            req = EmailRequest(language=lang,email="test@example.com",stops=[dict(
                order=1,id="merchant-test",name="대양상회",address="부산 중구 테스트로 1",category="식당")])
            body=build_email_body(req)
            self.assertIn("대양상회", body)
            if lang == "ko": self.assertNotIn("Daeyangsanghoe",body)
            else: self.assertIn(EMAIL_COPY[lang]["romanized_name"]+": Daeyangsanghoe",body)

    def test_mail_does_not_add_automatic_name_when_official_name_exists(self):
        official=next(p for p in LABELS if p["translations"].get("en", {}).get("name"))
        req=EmailRequest(language="en",email="test@example.com",stops=[dict(order=1,id=official["id"],
            name=official["name_ko"],address=official["address_ko"],category="관광명소")])
        body=build_email_body(req)
        self.assertIn(official["translations"]["en"]["name"], body)
        self.assertNotIn(EMAIL_COPY["en"]["romanized_name"],body)


if __name__ == "__main__": unittest.main()
