"""Gemini translation must use the native API endpoint and expose useful API errors."""

import unittest
from unittest.mock import patch

from backend import providers as P


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.is_error = status_code >= 400
        self.text = str(payload)

    def json(self):
        return self.payload


class GeminiNativeApiTest(unittest.TestCase):
    @patch("backend.providers.httpx.post")
    def test_gemini_uses_native_generate_content_endpoint(self, post):
        post.return_value = FakeResponse({
            "candidates": [{"content": {"parts": [{"text": "[{\"km\":\"សួស្តី\"}]"}]}}]
        })
        result = P._chat({"key_gemini": "test-secret"}, "gemini", "translate this")
        self.assertEqual(result, "[{\"km\":\"សួស្តី\"}]")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent")
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-secret")
        self.assertNotIn("test-secret", args[0])
        self.assertEqual(kwargs["json"]["contents"][0]["parts"][0]["text"], "translate this")
        self.assertEqual(kwargs["json"]["generationConfig"]["responseMimeType"], "application/json")

    @patch("backend.providers.httpx.post")
    def test_gemini_http_error_includes_provider_message(self, post):
        post.return_value = FakeResponse({"error": {"message": "model is not available"}}, 404)
        with self.assertRaisesRegex(RuntimeError, "Gemini API HTTP 404: model is not available"):
            P._chat({"key_gemini": "test-secret"}, "gemini", "translate this")


if __name__ == "__main__":
    unittest.main()
