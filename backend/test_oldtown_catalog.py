import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

from app.data_loader import load_places, load_opening_hours
from app.services.route import next_places, rotate_merchants
from app.services.walking import estimated_leg
from fastapi.encoders import jsonable_encoder

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("merge_oldtown",ROOT/"scripts/merge_oldtown_places.py")
merge=importlib.util.module_from_spec(spec);spec.loader.exec_module(merge)


class OldtownCatalogTests(unittest.TestCase):
    def test_catalog_covers_four_districts_and_preserves_existing_food_prices(self):
        places=load_places()
        self.assertEqual(set(places.district),{"중구","동구","서구","영도구"})
        self.assertTrue(places.id.is_unique)
        self.assertEqual(places[places.category.isin(["식당","카페·디저트"])].estimated_spend.notna().sum(),438)
        self.assertEqual(set(load_opening_hours().place_id)-set(places.id),set())

    def test_loader_rejects_other_district_and_invalid_fee(self):
        load_places.cache_clear()
        actual=pd.read_csv(ROOT/"data/processed/fin/places.csv",encoding="utf-8-sig")
        for field,value in [("address","부산광역시 해운대구 테스트로 1"),("admission_fee_krw",-1),("district","서구")]:
            frame=actual.copy();frame.loc[0,field]=value
            with self.subTest(field=field),patch("app.data_loader.pd.read_csv",return_value=frame):
                load_places.cache_clear()
                with self.assertRaises(ValueError):load_places()
        load_places.cache_clear()

    def test_other_district_candidates_and_fee_zero_are_json_safe(self):
        catalog=load_places();target=catalog[(catalog.district=="영도구") & (catalog.name=="국립해양박물관")].iloc[0]
        with patch("app.services.route.walking_leg",side_effect=estimated_leg):
            result=next_places(catalog,target.lat,target.lon,[],"관광명소",180,language="en")
        payload=json.loads(json.dumps(jsonable_encoder(result),allow_nan=False))
        museum=next(x for x in payload["alternatives"] if x["name"]=="국립해양박물관")
        self.assertEqual(museum["admission_fee_krw"],0)
        self.assertEqual(museum["district"],"영도구")
        self.assertEqual(museum["payment_status"],"not_verified")
        self.assertTrue(museum["opening_hours"])

    def test_rotation_keeps_nonmerchant_slots_and_only_rotates_registered_shops(self):
        rows=[dict(id="mall",payment_status="not_accepted"),dict(id="a",payment_status="merchant_listed"),dict(id="b",payment_status="merchant_listed"),dict(id="c",payment_status="merchant_listed")]
        with patch("app.services.route.rotate",return_value=list(reversed(rows[1:]))) as rotate:
            self.assertEqual([x["id"] for x in rotate_merchants(rows)],["mall","c","b"])
            self.assertEqual(rotate.call_args.args[0],rows[1:])
        with patch("app.services.route.rotate") as rotate:
            self.assertEqual(rotate_merchants(rows[:1]),rows[:1]);rotate.assert_not_called()

    def test_merge_preserves_unrelated_prices_and_ids_and_is_repeatable(self):
        _,places=merge.read(ROOT/"data/processed/fin/places.csv")
        _,research=merge.read(merge.RAW)
        _,locs=merge.read(merge.SUPPORT/"oldtown_locations.csv")
        _,rules=merge.read(merge.SUPPORT/"duration_rules.csv");rules={x["visit_type"].strip():x["duration_min"] for x in rules}
        locs={x["raw_id"]:x for x in locs}
        food=next(x for x in places if x["category"]=="식당" and x["estimated_spend"])
        raw=next(x for x in research if x["name"]=="송도해상케이블카")
        _,result,audit=merge.merge([food],[raw],locs,rules)
        self.assertEqual(result[0],food)
        self.assertEqual(audit[0]["action"],"added")
        _,again,_=merge.merge(result,[raw],locs,rules);self.assertEqual(again,result)
        bad={**raw,"existing_place_id":food["id"]}
        with self.assertRaises(ValueError):merge.merge([food],[bad],locs,rules)

    def test_uncertain_fees_and_complex_hours_are_not_made_definite(self):
        _,research=merge.read(merge.RAW)
        for name in ["아르떼뮤지엄 부산","송도용궁구름다리"]:
            values=merge.fee_values(next(x for x in research if x["name"]==name))
            self.assertEqual(values["admission_fee_status"],"conditional")
            self.assertEqual(values["admission_fee_krw"],"")
        for name in ["국제시장","송도해상케이블카","일성모자점"]:
            raw=next(x for x in research if x["name"]==name)
            self.assertEqual(merge.weekly_rows(raw,"test"),[])
        park=next(x for x in research if x["name"]=="용두산공원")
        rows=merge.weekly_rows(park,"test");self.assertEqual(len(rows),7)
        self.assertTrue(all(x["closes_next_day"]=="1" for x in rows))


if __name__=="__main__":unittest.main()
