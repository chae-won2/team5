import unittest
from unittest.mock import patch
import requests
from fastapi import HTTPException
from app.routers import geocode

class MapRegionTests(unittest.TestCase):
    def setUp(self): geocode.lookup_region.cache_clear()
    def tearDown(self): geocode.lookup_region.cache_clear()

    @patch.object(geocode,'KAKAO_KEY','test-key')
    @patch.object(geocode.requests,'get')
    def test_administrative_dong_and_cache(self,get):
        get.return_value.json.return_value={'documents':[{'region_type':'B','region_2depth_name':'중구','region_3depth_name':'신창동1가'},{'region_type':'H','region_2depth_name':'중구','region_3depth_name':'광복동'}]}
        for _ in range(2): self.assertEqual(geocode.map_region(35.1,129.03),{'district':'중구','dong':'광복동'})
        self.assertEqual(get.call_count,1)
        self.assertEqual(get.call_args.kwargs['params'],{'x':129.03,'y':35.1,'input_coord':'WGS84'})
        get.return_value.json.return_value={'documents':[{'region_type':'H','region_2depth_name':'영도구','region_3depth_name':'동삼1동'}]}
        self.assertEqual(geocode.map_region(35.08,129.07)['district'],'영도구')

    @patch.object(geocode,'KAKAO_KEY','test-key')
    @patch.object(geocode.requests,'get')
    def test_no_land_region_is_not_replaced_with_an_unrelated_dong(self,get):
        for docs in [[],[{'region_type':'B','region_3depth_name':'법정동'}]]:
            geocode.lookup_region.cache_clear();get.return_value.json.return_value={'documents':docs}
            self.assertEqual(geocode.lookup_region(0,0),{'district':'','dong':''})

    @patch.object(geocode,'KAKAO_KEY','test-key')
    @patch.object(geocode.requests,'get')
    def test_errors_are_not_cached_or_exposed(self,get):
        get.side_effect=requests.Timeout('secret upstream detail')
        for _ in range(2):
            with self.assertRaises(HTTPException) as error: geocode.lookup_region(35,129)
            self.assertEqual(error.exception.status_code,502);self.assertNotIn('secret',error.exception.detail)
        self.assertEqual(get.call_count,2)

    @patch.object(geocode,'KAKAO_KEY',None)
    @patch.object(geocode.requests,'get')
    def test_missing_configuration(self,get):
        with self.assertRaises(HTTPException) as error:geocode.lookup_region(35,129)
        self.assertEqual(error.exception.status_code,503);get.assert_not_called()

    def test_invalid_coordinates_are_rejected_before_lookup(self):
        import asyncio,httpx
        from fastapi import FastAPI
        app=FastAPI();app.include_router(geocode.router)
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                for query in ['lat=91&lon=129','lat=35&lon=181','lat=nan&lon=129','lat=35&lon=inf','lon=129']:
                    self.assertEqual((await client.get('/api/geocode/region?'+query)).status_code,422)
        with patch.object(geocode,'lookup_region') as lookup:
            asyncio.run(check());lookup.assert_not_called()

if __name__=='__main__':unittest.main()