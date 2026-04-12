import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app


class NoAuthApiTests(unittest.TestCase):
    def test_strategy_list_is_accessible_without_token(self):
        with patch('app.models.db.init_market_db', lambda: None), patch('app.core.scheduler.init_scheduler', lambda: None):
            with TestClient(create_app()) as client:
                response = client.get('/api/strategy/list')

        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json())


if __name__ == '__main__':
    unittest.main()
