import json
import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GBrainKnowledge:
    RESULT_LINE = re.compile(r"^\[(?P<score>\d+(?:\.\d+)?)\]\s+(?P<title>[^-]+?)\s+--\s+(?P<summary>.*)$")

    def __init__(self, repo_path: str, timeout_seconds: int = 5):
        self.repo_path = repo_path
        self.timeout_seconds = timeout_seconds

    def retrieve(self, query: str, scope: Optional[str] = None) -> Dict[str, Any]:
        try:
            gbrain_bin = self._resolve_gbrain_bin()
            if not gbrain_bin:
                return self._degraded(query, scope, "gbrain binary not found")

            cmd_query = query
            if scope and scope != "default":
                cmd_query = f"[{scope}] {query}"

            errors: List[str] = []
            items: List[Dict[str, Any]] = []
            for command in ("query", "search"):
                try:
                    result = subprocess.run(
                        [gbrain_bin, command, cmd_query],
                        cwd=self.repo_path,
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=self.timeout_seconds,
                    )
                except subprocess.TimeoutExpired:
                    errors.append(f"gbrain {command} timeout after {self.timeout_seconds}s")
                    continue

                if result.returncode != 0:
                    errors.append((result.stderr or f"gbrain {command} failed").strip())
                    continue

                items = self._parse_output(result.stdout)
                if items:
                    break
                errors.append(f"gbrain {command} returned no parsable results")

            if not items:
                logger.warning("Failed to parse GBrain output or no results returned")
                return self._degraded(query, scope, "; ".join(errors) or "no parsable gbrain results")

            return {
                "query": query,
                "scope": scope or "default",
                "items": items,
                "degraded": False,
            }
        except Exception as exc:
            logger.error("GBrain retrieve failed: %s", exc)
            return self._degraded(query, scope, str(exc))

    def _resolve_gbrain_bin(self) -> Optional[str]:
        bun_bin = str(Path.home() / ".bun" / "bin")
        return shutil.which("gbrain") or shutil.which("gbrain", path=bun_bin)

    def _parse_output(self, stdout: str) -> List[Dict[str, Any]]:
        json_items = self._parse_json_output(stdout)
        if json_items:
            return self._sanitize_items(json_items)
        return self._parse_text_output(stdout)

    @staticmethod
    def _parse_json_output(stdout: str) -> Optional[List[Dict[str, Any]]]:
        output = (stdout or "").strip()
        start_idx = -1
        for idx, char in enumerate(output):
            if char in ("{", "["):
                start_idx = idx
                break
        if start_idx < 0:
            return None
        try:
            data = json.loads(output[start_idx:])
        except json.JSONDecodeError:
            return None
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            results = data.get("results", [])
            return results if isinstance(results, list) else []
        return []

    def _parse_text_output(self, stdout: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        normalized = (stdout or "").replace("\\n", "\n")
        chunks = re.split(r"(?=^\[\d+(?:\.\d+)?\]\s)", normalized, flags=re.MULTILINE)
        for chunk in chunks:
            line = chunk.strip().splitlines()[0] if chunk.strip() else ""
            match = self.RESULT_LINE.match(line)
            if not match:
                continue
            item: Dict[str, Any] = {
                "title": match.group("title").strip()[:120],
                "summary": match.group("summary").strip()[:400],
            }
            try:
                item["score"] = float(match.group("score"))
            except ValueError:
                pass
            items.append(item)
            if len(items) >= 8:
                break
        return items

    @staticmethod
    def _sanitize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        safe_items: List[Dict[str, Any]] = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            safe: Dict[str, Any] = {}
            title = item.get("title") or item.get("name") or "未命名知识"
            summary = item.get("summary") or item.get("snippet") or item.get("excerpt") or ""
            if isinstance(title, str):
                safe["title"] = title[:120]
            if isinstance(summary, str):
                safe["summary"] = summary[:400]
            score = item.get("score")
            if isinstance(score, (int, float)):
                safe["score"] = score
            if safe:
                safe_items.append(safe)
        return safe_items

    @staticmethod
    def _degraded(query: str, scope: Optional[str], error: str) -> Dict[str, Any]:
        return {
            "query": query,
            "scope": scope or "default",
            "degraded": True,
            "items": [],
            "error": error,
        }

    def learn(self, title: str, summary: str, scope: Optional[str] = None) -> bool:
        """Store new experience rules into GBrain."""
        try:
            gbrain_bin = self._resolve_gbrain_bin()
            if not gbrain_bin:
                logger.warning("gbrain binary not found, skipping learning.")
                return False

            cmd = [gbrain_bin, "add", "--title", title, "--summary", summary]
            if scope:
                cmd.extend(["--scope", scope])
                
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=self.timeout_seconds,
            )
            if result.returncode != 0:
                logger.error(f"GBrain learn failed: {result.stderr}")
                return False
            return True
        except Exception as exc:
            logger.error(f"GBrain learn exception: {exc}")
            return False

    def learn_from_review(self, review_result: Any) -> int:
        """Extract issues from ReviewResult and inject them as adversarial experience into GBrain."""
        count = 0
        for issue in getattr(review_result, "issues", []):
            title = f"Adversarial Review Finding: {issue.summary}"
            summary = f"Rule derived from failed review: {issue.recommendation}. Relates to: {', '.join(issue.related_requirement_ids)}"
            if self.learn(title, summary, scope="adversarial"):
                count += 1
        return count
