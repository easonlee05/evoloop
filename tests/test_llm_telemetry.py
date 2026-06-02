import json
import unittest
from unittest.mock import patch

from app.services.llm import OpenAILLM


class FakeStreamResponse:
    def __init__(self, status_code=200, lines=None, content=b""):
        self.status_code = status_code
        self._lines = lines or []
        self.content = content
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def iter_lines(self):
        for line in self._lines:
            yield line


class OpenAILLMTelemetryTests(unittest.TestCase):
    def test_stream_chat_route_emits_timing_and_throughput_telemetry(self):
        response = FakeStreamResponse(
            status_code=200,
            lines=[
                b'data: {"choices":[{"delta":{"content":"hello"}}]}',
                b'data: {"choices":[{"delta":{"content":" world"}}]}',
                b'data: [DONE]',
            ],
        )
        telemetry_events = []

        with patch("requests.post", return_value=response) as post:
            llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")
            chunks = list(llm.invoke_stream("PM", "draft", {"title": "诊断", "goal": "测速"}, telemetry=lambda event, payload: telemetry_events.append((event, payload))))

        self.assertEqual(chunks, ["hello", " world"])
        self.assertEqual(post.call_count, 1)
        event_names = [event for event, _ in telemetry_events]
        self.assertEqual(event_names[0], "llm.call.started")
        self.assertIn("llm.call.headers_received", event_names)
        self.assertIn("llm.call.first_token", event_names)
        self.assertEqual(event_names[-1], "llm.call.completed")
        completed = telemetry_events[-1][1]
        self.assertEqual(completed["output_chars"], 11)
        self.assertEqual(completed["chunk_count"], 2)
        self.assertEqual(completed["base_url_host"], "relay.example.test")
        self.assertNotIn("api_key", completed)

    def test_writer_anthropic_fallback_uses_large_document_token_budget(self):
        unsupported = json.dumps({"error": {"message": "不支持 Api格式"}}).encode("utf-8")
        responses = [
            FakeStreamResponse(status_code=400, content=unsupported),
            FakeStreamResponse(
                status_code=200,
                lines=[
                    b'data: {"type":"content_block_delta","delta":{"text":"doc"}}',
                    b'data: {"type":"message_stop"}',
                ],
            ),
        ]
        captured_payloads = []

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured_payloads.append({"url": url, "json": json, "timeout": timeout})
            return responses.pop(0)

        with patch("requests.post", side_effect=fake_post):
            llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")
            chunks = list(llm.invoke_stream("Writer", "write final PRD", {"title": "长文档", "goal": "完整输出"}))

        self.assertEqual(chunks, ["doc"])
        self.assertEqual(captured_payloads[1]["url"], "https://relay.example.test/api/v1/messages")
        self.assertGreaterEqual(captured_payloads[1]["json"]["max_tokens"], 16000)

    def test_non_writer_anthropic_fallback_keeps_compact_token_budget(self):
        unsupported = json.dumps({"error": {"message": "不支持 Api格式"}}).encode("utf-8")
        responses = [
            FakeStreamResponse(status_code=400, content=unsupported),
            FakeStreamResponse(status_code=200, lines=[b'data: {"type":"content_block_delta","delta":{"text":"ok"}}']),
        ]
        captured_payloads = []

        def fake_post(url, json=None, headers=None, stream=None, timeout=None):
            captured_payloads.append({"url": url, "json": json})
            return responses.pop(0)

        with patch("requests.post", side_effect=fake_post):
            llm = OpenAILLM(api_key="secret", base_url="https://relay.example.test/api/v1")
            list(llm.invoke_stream("PM", "draft", {"title": "短评审", "goal": "挑战风险"}))

        self.assertEqual(captured_payloads[1]["json"]["max_tokens"], 4096)


if __name__ == "__main__":
    unittest.main()
