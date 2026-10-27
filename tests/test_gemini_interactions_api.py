"""Gemini translation uses Interactions API and exposes useful API errors."""

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


class GeminiInteractionsApiTest(unittest.TestCase):
    @patch("backend.providers.httpx.post")
    def test_gemini_uses_interactions_api_and_current_model(self, post):
        post.return_value = FakeResponse({
            "status": "completed",
            "steps": [{"type": "model_output", "content": [
                {"type": "text", "text": "[{\"km\":\"សួស្តី\",\"char\":\"旁白\"}]"}
            ]}],
        })
        # A saved 2.5 model is migrated automatically, without needing the user to re-edit Settings.
        cfg = {"key_gemini": "test-secret", "standard_translate_model_gemini": "gemini-2.5-flash"}
        result = P._chat(cfg, "gemini", "translate this")
        self.assertEqual(result, "[{\"km\":\"សួស្តី\",\"char\":\"旁白\"}]")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-secret")
        self.assertNotIn("test-secret", args[0])
        self.assertEqual(kwargs["json"]["model"], "gemini-3.8-flash")
        self.assertEqual(kwargs["json"]["input"], "translate this")
        self.assertEqual(kwargs["json"]["response_format"]["mime_type"], "application/json")
        self.assertEqual(P.model_for(cfg, "translate", "gemini"), "gemini-3.8-flash")

    @patch("backend.providers.httpx.post")
    def test_gemini_http_error_includes_provider_message(self, post):
        post.return_value = FakeResponse({"error": {"message": "model is not available"}}, 404)
        with self.assertRaisesRegex(RuntimeError, "Gemini API HTTP 404: model is not available"):
            P._chat({"key_gemini": "test-secret"}, "gemini", "translate this")


if __name__ == "__main__":
    unittest.main()
