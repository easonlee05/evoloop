import json
import subprocess
import unittest
from unittest.mock import patch

from app.services.gbrain_service import GBrainKnowledge


class GBrainKnowledgeTests(unittest.TestCase):
    def test_cli_timeout_degrades_instead_of_hanging(self):
        knowledge = GBrainKnowledge("/tmp")

        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", side_effect=[subprocess.TimeoutExpired(cmd=["gbrain"], timeout=5), subprocess.TimeoutExpired(cmd=["gbrain"], timeout=5)]):
                result = knowledge.retrieve("风控")

        self.assertTrue(result["degraded"])
        self.assertEqual(result["items"], [])
        self.assertIn("timeout", result["error"].lower())

    def test_invalid_json_degrades_without_returning_raw_output(self):
        knowledge = GBrainKnowledge("/tmp")
        completed = subprocess.CompletedProcess(
            args=["gbrain", "search"],
            returncode=0,
            stdout="not-json at all",
            stderr="",
        )

        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", return_value=completed):
                result = knowledge.retrieve("结算")

        self.assertTrue(result["degraded"])
        self.assertEqual(result["items"], [])
        self.assertIn("no parsable", result["error"])

    def test_json_results_are_normalized_to_safe_summaries(self):
        knowledge = GBrainKnowledge("/tmp")
        payload = {
            "results": [
                {
                    "title": "规则 A",
                    "summary": "限流策略",
                    "path": "/secret/local/path.md",
                    "content": "full private material",
                    "score": 0.87,
                }
            ]
        }
        completed = subprocess.CompletedProcess(
            args=["gbrain", "search"],
            returncode=0,
            stdout=json.dumps(payload, ensure_ascii=False),
            stderr="",
        )

        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", return_value=completed):
                result = knowledge.retrieve("限流")

        self.assertFalse(result["degraded"])
        self.assertEqual(result["items"][0]["title"], "规则 A")
        self.assertEqual(result["items"][0]["summary"], "限流策略")
        self.assertEqual(result["items"][0]["score"], 0.87)
        self.assertNotIn("path", result["items"][0])
        self.assertNotIn("content", result["items"][0])

    def test_text_results_are_parsed_into_safe_items(self):
        knowledge = GBrainKnowledge("/tmp")
        completed = subprocess.CompletedProcess(
            args=["gbrain", "query"],
            returncode=0,
            stdout="[1.2345] agent_map -- # Agent Map\\n[0.9988] readme -- # PM-Agent Platform Backend\\n",
            stderr="",
        )

        with patch("app.services.gbrain_service.shutil.which", side_effect=[None, "/tmp/fake-gbrain"]):
            with patch("app.services.gbrain_service.subprocess.run", return_value=completed):
                result = knowledge.retrieve("WorkflowEngine")

        self.assertFalse(result["degraded"])
        self.assertEqual(result["items"][0]["title"], "agent_map")
        self.assertEqual(result["items"][0]["summary"], "# Agent Map")


if __name__ == "__main__":
    unittest.main()
