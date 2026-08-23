import unittest
from unittest.mock import patch

from harness.providers.ollama import OllamaProvider


class OllamaProviderTests(unittest.TestCase):
    PARAMETERS = {
        "temperature": 1.0,
        "top_p": 1.0,
        "top_k": 40,
        "max_tokens": 12,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "seed": None,
        "stop": ["\n"],
    }
    EXPECTED_OPTIONS = {
        "temperature": 1.0,
        "top_p": 1.0,
        "top_k": 40,
        "num_predict": 12,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "stop": ["\n"],
    }

    def test_base_uses_native_raw_generate_with_literal_prompt(self):
        provider = OllamaProvider()
        body = {
            "model": "base-model", "created_at": "2026-08-22T12:34:56Z",
            "response": "KEMAR", "done": True, "done_reason": "stop",
            "prompt_eval_count": 101, "eval_count": 3,
            "total_duration": 1000, "load_duration": 100,
            "prompt_eval_duration": 400, "eval_duration": 500,
        }
        with patch("harness.providers.ollama._json_request", return_value=body) as request:
            result = provider.sample(
                model="base-model", interface="completion", payload="raw transcript",
                parameters=self.PARAMETERS, max_attempts=1,
            )
        url = request.call_args.args[0]
        sent = request.call_args.kwargs["body"]
        self.assertTrue(url.endswith("/api/generate"))
        self.assertFalse(url.endswith("/v1/completions"))
        self.assertEqual(sent["prompt"], "raw transcript")
        self.assertIs(sent["raw"], True)
        self.assertIs(sent["stream"], False)
        self.assertEqual(sent["options"], self.EXPECTED_OPTIONS)
        self.assertNotIn("seed", sent["options"])
        for forbidden in ("messages", "template", "system"):
            self.assertNotIn(forbidden, sent)

        self.assertEqual(result.requested_model, "base-model")
        self.assertEqual(result.actual_model, "base-model")
        self.assertEqual(result.client, "ollama_native_generate_raw")
        self.assertEqual(result.raw_response, "KEMAR")
        self.assertEqual(result.finish_reason, "stop")
        self.assertIsNone(result.response_id)
        self.assertEqual(result.provider_timestamp, "2026-08-22T12:34:56Z")
        self.assertEqual(result.usage, {
            "prompt_tokens": 101,
            "completion_tokens": 3,
            "total_tokens": 104,
            "total_duration_ns": 1000,
            "load_duration_ns": 100,
            "prompt_eval_duration_ns": 400,
            "eval_duration_ns": 500,
        })
        self.assertEqual(result.sent_parameters, sent)

    def test_instruction_model_uses_native_chat_with_unchanged_messages(self):
        provider = OllamaProvider()
        body = {
            "model": "chat-model", "created_at": "2026-08-22T12:35:56Z",
            "message": {"role": "assistant", "content": "DOVIC"},
            "done": True, "done_reason": "stop",
            "prompt_eval_count": 88, "eval_count": 2,
            "total_duration": 900, "load_duration": 90,
            "prompt_eval_duration": 350, "eval_duration": 460,
        }
        messages = [{"role": "user", "content": "test"}]
        with patch("harness.providers.ollama._json_request", return_value=body) as request:
            result = provider.sample(
                model="chat-model", interface="chat", payload=messages,
                parameters=self.PARAMETERS, max_attempts=1,
            )
        url = request.call_args.args[0]
        sent = request.call_args.kwargs["body"]
        self.assertTrue(url.endswith("/api/chat"))
        self.assertFalse(url.endswith("/v1/chat/completions"))
        self.assertEqual(sent["messages"], messages)
        self.assertIs(sent["stream"], False)
        self.assertEqual(sent["options"], self.EXPECTED_OPTIONS)
        self.assertNotIn("seed", sent["options"])
        self.assertNotIn("prompt", sent)
        self.assertNotIn("raw", sent)
        self.assertEqual(result.raw_response, "DOVIC")
        self.assertEqual(result.finish_reason, "stop")
        self.assertEqual(result.client, "ollama_native_chat")
        self.assertEqual(result.provider_timestamp, "2026-08-22T12:35:56Z")
        self.assertEqual(result.usage["total_tokens"], 90)
        self.assertEqual(result.sent_parameters, sent)


if __name__ == "__main__":
    unittest.main()
