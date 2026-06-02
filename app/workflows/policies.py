"""Reusable workflow and tool-policy helpers for task definitions."""
from __future__ import annotations

from app.core.tools import ToolPolicy, ToolPolicyRule


COMMON_READ_TOOLS = ["material.read", "material.parse", "knowledge.retrieve", "artifact.read"]
COMMON_WRITE_TOOLS = ["artifact.write", "artifact.backup", "diff.extract_rules", "event.emit"]


def build_default_tool_policy(task_type: str) -> ToolPolicy:
    return ToolPolicy(
        task_type=task_type,
        rules=[
            ToolPolicyRule(role="SYSTEM", step_id="*", allowed_tools=["material.parse", "knowledge.retrieve", "event.emit"]),
            ToolPolicyRule(role="PM", step_id="*", allowed_tools=["material.read", "knowledge.retrieve", "artifact.read"]),
            ToolPolicyRule(role="Tech", step_id="*", allowed_tools=["knowledge.retrieve", "artifact.read"]),
            ToolPolicyRule(role="QA", step_id="*", allowed_tools=["material.read", "artifact.read"]),
            ToolPolicyRule(role="Reviewer", step_id="*", allowed_tools=["artifact.read", "format.validate", "event.emit"]),
            ToolPolicyRule(role="Writer", step_id="*", allowed_tools=["artifact.read", "artifact.write", "artifact.backup"]),
        ],
    )
