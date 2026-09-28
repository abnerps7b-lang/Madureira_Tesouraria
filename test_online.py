import json
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import banco_online as bank
import sessoes_online as sessions
import Testes as app


class OnlineTests(unittest.TestCase):
    def test_sum_bigint_serializes_as_integer(self):
        make = bank.row_factory(SimpleNamespace(description=[SimpleNamespace(name='total')]))
        row = make([Decimal('9876543210123')])
        self.assertEqual(row[0], row['total'])
        self.assertEqual(json.loads(json.dumps(row))['total'], 9876543210123)

    def test_session_shared_revoked_expired_and_password_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sessions.db'
            @contextmanager
            def connect():
                con = sqlite3.connect(path)
                con.row_factory = sqlite3.Row
                try:
                    with con:
                        yield con
                finally:
                    con.close()
            with connect() as con:
                con.execute('CREATE TABLE sessoes(token TEXT PRIMARY KEY,expira INTEGER,credencial TEXT)')
                con.execute('CREATE TABLE tentativas_login(chave TEXT PRIMARY KEY,inicio INTEGER,quantidade INTEGER)')
            with patch.object(sessions, 'connect_online', connect), patch.dict(os.environ, {'ADMIN_PASSWORD': 'senha-de-teste-online'}, clear=True):
                token = sessions.create_session()
                app.SESSIONS.clear()
                self.assertTrue(sessions.authenticated(token))
                with connect() as con:
                    self.assertNotEqual(con.execute('SELECT token FROM sessoes').fetchone()[0], token)
                with patch.dict(os.environ, {'ADMIN_PASSWORD': 'outra-senha-de-teste'}):
                    self.assertFalse(sessions.authenticated(token))
                sessions.logout(token)
                self.assertFalse(sessions.authenticated(token))
                token = sessions.create_session()
                with connect() as con:
                    con.execute('UPDATE sessoes SET expira=0')
                self.assertFalse(sessions.authenticated(token))
                for _ in range(10):
                    self.assertTrue(sessions.allow_attempt('test-ip'))
                self.assertFalse(sessions.allow_attempt('test-ip'))
                sessions.reset_attempts('test-ip')
                self.assertTrue(sessions.allow_attempt('test-ip'))

    def test_vercel_without_database_returns_json_and_creates_no_sqlite(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'VERCEL': '1'}, clear=True), patch.object(app, 'DB', Path(folder) / 'never.db'):
            server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                req = Request(f'http://127.0.0.1:{server.server_port}/api/login',
                              data=b'{"senha":"test"}', headers={'X-Requested-With': 'Igreja'})
                with self.assertRaises(HTTPError) as caught:
                    urlopen(req)
                response = caught.exception
                self.assertEqual(response.code, 503)
                self.assertIn('DATABASE_URL', json.loads(response.read())['error'])
                self.assertFalse(app.DB.exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_postgres_parameter_conversion_keeps_values_separate(self):
        class Raw:
            def execute(self, query, params=()):
                self.query, self.params = query, params
        raw = Raw()
        bank.Connection(raw).execute('SELECT * FROM despesas WHERE descricao=?', ("x'; DROP TABLE despesas; --",))
        self.assertEqual(raw.query, 'SELECT * FROM despesas WHERE descricao=%s')
        self.assertEqual(raw.params, ("x'; DROP TABLE despesas; --",))


if __name__ == '__main__':
    unittest.main()
