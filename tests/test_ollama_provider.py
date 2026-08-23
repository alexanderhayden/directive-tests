import unittest
from unittest.mock import patch

from harness.providers.ollama import OllamaProvider


class OllamaProviderTests(unittest.TestCase):
    def test_base_uses_raw_completion_endpoint_without_messages(self):
        provider = OllamaProvider()
        body = {
            "id": "local-1", "model": "base-model",
            "choices": [{"text": "KEMAR", "finish_reason": "stop"}], "usage": {},
        }
        with patch("harness.providers.ollama._json_request", return_value=body) as request:
            result = provider.sample(
                model="base-model", interface="completion", payload="raw transcript",
                parameters={"temperature": 1.0, "max_tokens": 12}, max_attempts=1,
            )
        url = request.call_args.args[0]
        sent = request.call_args.kwargs["body"]
        self.assertTrue(url.endswith("/v1/completions"))
        self.assertEqual(sent["prompt"], "raw transcript")
        self.assertNotIn("messages", sent)
        self.assertEqual(result.raw_response, "KEMAR")

    def test_instruction_model_uses_chat_endpoint(self):
        provider = OllamaProvider()
        body = {
            "id": "local-2", "model": "chat-model",
            "choices": [{"message": {"content": "DOVIC"}, "finish_reason": "stop"}], "usage": {},
        }
        messages = [{"role": "user", "content": "test"}]
        with patch("harness.providers.ollama._json_request", return_value=body) as request:
            result = provider.sample(
                model="chat-model", interface="chat", payload=messages,
                parameters={"temperature": 1.0, "max_tokens": 12}, max_attempts=1,
            )
        url = request.call_args.args[0]
        sent = request.call_args.kwargs["body"]
        self.assertTrue(url.endswith("/v1/chat/completions"))
        self.assertEqual(sent["messages"], messages)
        self.assertNotIn("prompt", sent)
        self.assertEqual(result.raw_response, "DOVIC")


if __name__ == "__main__":
    unittest.main()
