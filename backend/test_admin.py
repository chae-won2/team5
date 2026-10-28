import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.services.exposure import issue, acknowledge


class AdminDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EXPOSURE_DB_PATH': str(Path(self.temp.name) / 'exposure.sqlite3'),
                                            'EXPOSURE_DATABASE_URL': '', 'RENDER': ''})
        self.env.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_requires_key_and_hides_feature_when_unconfigured(self):
        with patch('app.routers.admin.ADMIN_DASHBOARD_KEY', None):
            self.assertEqual(self.client.get('/admin').status_code, 500)

    @patch('app.routers.admin.ADMIN_DASHBOARD_KEY', 'secret')
    def test_wrong_key_rejected_and_sections_render(self):
        self.assertEqual(self.client.get('/admin?key=wrong').status_code, 403)
        token = issue([{'id': 'a', 'leg_seconds': 60}])
        acknowledge(token)
        response = self.client.get('/admin?key=secret')
        self.assertEqual(response.status_code, 200)
        self.assertIn('요약 지표', response.text)
        self.assertIn('지역상권 현황', response.text)
        self.assertIn('추천 요청 1건', response.text)
        self.assertIn('표시 확인 1건', response.text)
        self.assertIn('데이터 신뢰성 관리', response.text)
        # First week has no prior window to compare against, so the trend badge is honest, not fabricated.
        self.assertIn('>신규<', response.text)


if __name__ == '__main__':
    unittest.main()
