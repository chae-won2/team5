import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app
from app.services.exposure import rotate, issue, acknowledge, counts, window_summary, database, ExposureStorageError, PostgresConnection, WINDOW_SECONDS
from app.data_loader import load_places
from app.services.route import next_places


class ExposureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'EXPOSURE_DB_PATH':str(Path(self.temp.name)/'exposure.sqlite3'),
                                         'EXPOSURE_DATABASE_URL':'', 'RENDER':''})
        self.env.start()
        self.places = [{'id':i,'leg_minutes':s/60,'leg_seconds':s} for i,s in
                       [('a',300),('b',360),('c',420),('far',421)]]

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_ack_once_rotation_and_distance_boundary(self):
        first = rotate(self.places)
        self.assertEqual([p['id'] for p in first],['a','b','c'])
        token = issue(first)
        self.assertEqual(counts(), {})  # API generation is not an impression.
        self.assertTrue(acknowledge(token))
        self.assertFalse(acknowledge(token))
        self.assertEqual(counts(), {'a':(1,1),'b':(0,1),'c':(0,1)})
        self.assertEqual([p['id'] for p in rotate(self.places)],['b','c','a'])
        # A fresh database connection retains the acknowledged list.
        self.assertEqual(counts()['a'],(1,1))

    def test_window_summary_splits_by_week(self):
        token = issue(self.places[:1])
        acknowledge(token)
        self.assertEqual(window_summary(0), {'requests_total': 1, 'requests_shown': 1, 'places': {'a': (1, 1)}})
        self.assertEqual(window_summary(1), {'requests_total': 0, 'requests_shown': 0, 'places': {}})
        with patch('app.services.exposure.time.time', return_value=time.time() + WINDOW_SECONDS):
            self.assertEqual(window_summary(0)['requests_total'], 0)
            self.assertEqual(window_summary(1)['requests_total'], 1)

    def test_endpoint_validation_and_expired_history(self):
        client = TestClient(app)
        self.assertEqual(client.post('/api/recommend/impressions',json={'recommendation_id':'fake'}).status_code,422)
        self.assertEqual(client.post('/api/recommend/impressions',json={'recommendation_id':'00000000-0000-0000-0000-000000000000'}).status_code,404)
        token=issue(self.places[:1])
        with patch('app.services.exposure.time.time',return_value=10**12):
            with self.assertRaises(ValueError): acknowledge(token)
        acknowledge(token)
        with patch('app.services.exposure.time.time',return_value=10**12):
            self.assertEqual(counts(),{})

    def test_cloud_requires_database_and_history_is_retained(self):
        with patch.dict(os.environ, {'RENDER':'true'}):
            with self.assertRaises(ExposureStorageError): counts()
        token=issue(self.places[:1]); acknowledge(token)
        with patch('app.services.exposure.time.time',return_value=10**12):
            issue(self.places[:1])
        with database() as db:
            self.assertIsNotNone(db.execute('SELECT shown FROM lists WHERE id=?',(token,)).fetchone())

    def test_postgres_statements_parameterize_values(self):
        from unittest.mock import Mock
        connection=Mock()
        PostgresConnection(connection).execute('INSERT INTO lists(id,created,places) VALUES (?,?,?)',('id',1,'[]'))
        connection.execute.assert_called_once_with('INSERT INTO app_private.exposure_lists(id,created,places) VALUES (%s,%s,%s)',('id',1,'[]'))

    def test_database_errors_do_not_expose_credentials(self):
        import psycopg
        with patch.dict(os.environ, {'EXPOSURE_DATABASE_URL':'postgresql://private-secret'}), \
                patch('psycopg.connect',side_effect=psycopg.OperationalError('private-secret')):
            with self.assertRaises(ExposureStorageError) as error: counts()
            self.assertNotIn('private-secret',str(error.exception))

    def test_candidates_assignment_display_and_simulation_are_separate(self):
        pool = [{**p, 'duration_min':30, 'projected_total_seconds':p['leg_seconds']+1800} for p in self.places]
        token = issue(pool[:3], candidates=pool, policy='rotation', context={'category':'카페/디저트'})
        with database() as db:
            row = db.execute('SELECT policy,policy_version,mode,run_id,context,shown FROM lists WHERE id=?',(token,)).fetchone()
            self.assertEqual(row[:4],('rotation','rotation_v1','production',None))
            self.assertIsNone(row[-1])
            candidates = db.execute('SELECT place_id,walk_seconds,assigned_rank,expected_exposure FROM candidates WHERE request_id=? ORDER BY place_id',(token,)).fetchall()
            self.assertEqual(len(candidates),4)
            self.assertEqual(next(p[2] for p in candidates if p[0]=='far'),None)
            self.assertTrue(all(p[3]==0.75 for p in candidates))
        self.assertEqual(counts(),{})
        acknowledge(token)
        before = counts()
        experiment = issue(pool[1:4], candidates=pool, policy='distance',mode='simulation',run_id='trial-1')
        acknowledge(experiment)
        self.assertEqual(counts(),before)
        with self.assertRaises(ValueError):
            issue(pool[:3], candidates=pool[:-2],policy='rotation')
        with self.assertRaises(ValueError):
            issue([],policy='distance',mode='simulation')
        empty = issue([],candidates=[],policy='rotation')
        with database() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM candidates WHERE request_id=?',(empty,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM lists').fetchone()[0],3)

    def test_old_sqlite_history_is_migrated_without_fabricating_candidates(self):
        import sqlite3
        path = os.environ['EXPOSURE_DB_PATH']
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE lists (id TEXT PRIMARY KEY,created REAL NOT NULL,shown REAL,places TEXT NOT NULL)')
            db.execute("INSERT INTO lists VALUES ('old',1,2,'[\"a\"]')")
        db.close()
        with database() as db:
            self.assertEqual(db.execute("SELECT policy,mode,places FROM lists WHERE id='old'").fetchone(),('legacy','production','["a"]'))
            self.assertEqual(db.execute('SELECT count(*) FROM candidates').fetchone()[0],0)

    @patch('app.services.route.walking_leg')
    def test_next_route_rotates_without_mutating_fixed_stops(self, walk):
        # All three merchants remain feasible; fixed prefix is excluded. Uses a merchant
        # category because exposure rotation does not apply to 관광명소 (route.py).
        base={**load_places().iloc[0].to_dict(),'category':'식당','duration_min':30}
        import pandas as pd
        catalog=pd.DataFrame([{**base,'id':i,'lat':35.101+k*.001} for k,i in enumerate(['a','b','c','d'])])
        walk.return_value={'leg_minutes':5,'leg_seconds':300,'leg_path':[],'leg_distance_m':300}
        fixed=[catalog.iloc[0].to_dict()]
        first=next_places(catalog,35.1,129.03,fixed,'식당',180)
        acknowledge(issue(first['alternatives']))
        second=next_places(catalog,35.1,129.03,fixed,'식당',180)
        self.assertEqual([p['id'] for p in second['stops']],['a'])
        self.assertNotEqual(first['alternatives'][0]['id'],second['alternatives'][0]['id'])
        self.assertTrue(all(p['projected_total_minutes']<=180 and p['leg_seconds']<=1200 for p in second['alternatives']))

    @patch('app.services.route.walking_leg')
    def test_api_issues_list_then_acknowledges_once(self, walk):
        import pandas as pd
        # Uses a merchant category because exposure rotation does not apply to 관광명소.
        base={**load_places().iloc[0].to_dict(),'category':'식당','duration_min':30}
        catalog=pd.DataFrame([{**base,'id':i,'lat':35.101+k*.001} for k,i in enumerate(['a','b','c','d'])])
        walk.return_value={'leg_minutes':5,'leg_seconds':300,'leg_path':[],'leg_distance_m':300}
        client=TestClient(app)
        body={'start_lat':35.1,'start_lon':129.03,'category':'식당','max_minutes':180}
        with patch('app.routers.recommend.load_places',return_value=catalog):
            response=client.post('/api/recommend/next',json=body)
            self.assertEqual(response.status_code,200)
            first=response.json()
            self.assertEqual(counts(),{})
            self.assertNotIn('_candidate_snapshot',first)
            with database() as db:
                rows = db.execute('SELECT assigned_rank,expected_exposure FROM candidates WHERE request_id=?',(first['recommendation_id'],)).fetchall()
                self.assertEqual(len(rows),4)
                self.assertEqual(sum(rank is not None for rank,expected in rows),3)
                self.assertTrue(all(expected==0.75 for rank,expected in rows))
            payload={'recommendation_id':first['recommendation_id']}
            self.assertTrue(client.post('/api/recommend/impressions',json=payload).json()['recorded'])
            self.assertFalse(client.post('/api/recommend/impressions',json=payload).json()['recorded'])
            second=client.post('/api/recommend/next',json=body).json()
            self.assertNotEqual(first['alternatives'][0]['id'],second['alternatives'][0]['id'])


if __name__=='__main__': unittest.main()
