"""Safety checks for the ID-based price merge."""
import unittest
from merge_estimated_spend import merge_prices


class PriceMergeTests(unittest.TestCase):
    def setUp(self):
        self.place = {'id': 'a', 'name': '가게', 'category': '식당', 'estimated_spend': '', 'lat': '35.1'}
        self.source = {'장소 ID': 'a', '상호명': '가게', '카테고리': '식당', '1인 가격(원)': '12,000'}

    def test_match_preserves_other_fields_and_is_repeatable(self):
        untouched = {**self.place, 'id': 'b', 'estimated_spend': ''}
        result = merge_prices([self.place, untouched], [self.source])
        self.assertEqual(result, [{**self.place, 'estimated_spend': '12000'}, untouched])
        self.assertEqual(merge_prices(result, [self.source]), result)
        self.assertEqual(self.place['estimated_spend'], '')

    def test_bad_identity_or_price_is_rejected(self):
        for change in [{'장소 ID': 'missing'}, {'상호명': '다른 가게'}, {'카테고리': '카페·디저트'}, {'1인 가격(원)': '12000원'}, {'1인 가격(원)': '-1'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                merge_prices([self.place], [{**self.source, **change}])

    def test_conflicting_existing_price_is_not_overwritten(self):
        with self.assertRaises(ValueError):
            merge_prices([{**self.place, 'estimated_spend': '1000'}], [self.source])

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            merge_prices([self.place, self.place], [self.source])
        with self.assertRaises(ValueError):
            merge_prices([self.place], [self.source, self.source])


if __name__ == '__main__':
    unittest.main()
