import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import Testes as app


class LoginConfigTest(unittest.TestCase):
    def test_vercel_environment_password(self):
        with patch.dict(os.environ, {'VERCEL': '1', 'ADMIN_PASSWORD': 'senha-teste-acentuação'}, clear=True):
            self.assertTrue(app.verify_password('senha-teste-acentuação'))
            self.assertFalse(app.verify_password('incorreta'))

    def test_missing_and_short_password(self):
        with patch.dict(os.environ, {'VERCEL': '1'}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'ADMIN_PASSWORD'):
                app.verify_password('qualquer')
        with patch.dict(os.environ, {'VERCEL': '1', 'ADMIN_PASSWORD': ''}, clear=True):
            with self.assertRaisesRegex(RuntimeError, '12 caracteres'):
                app.verify_password('')

    def test_local_password_and_missing_config(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            path = Path(folder) / 'acesso.json'
            with patch.object(app, 'CONFIG', path):
                with self.assertRaises(RuntimeError):
                    app.verify_password('teste')
                path.write_text(json.dumps({'salt': 'test', 'hash': app.digest('teste', 'test')}))
                self.assertTrue(app.verify_password('teste'))
                self.assertFalse(app.verify_password('errada'))
