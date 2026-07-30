import unittest
import json
from app import app


class TestMultiplyFunction(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_multiply_valid_numbers(self):
        response = self.app.post(
            "/multiply",
            data=json.dumps({"a": 3, "b": 4}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["result"], 12.0)

    def test_multiply_zero(self):
        response = self.app.post(
            "/multiply",
            data=json.dumps({"a": 5, "b": 0}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["result"], 0.0)

    def test_multiply_negative_numbers(self):
        response = self.app.post(
            "/multiply",
            data=json.dumps({"a": -2, "b": 3}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["result"], -6.0)

    def test_multiply_missing_payload(self):
        response = self.app.post(
            "/multiply",
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_multiply_missing_fields(self):
        response = self.app.post(
            "/multiply",
            data=json.dumps({"a": 5}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_multiply_invalid_type(self):
        response = self.app.post(
            "/multiply",
            data=json.dumps({"a": "abc", "b": 5}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
