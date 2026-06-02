"""Registered Tool execution with ToolPolicy checks and audit events."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from app.core.context import TaskContext
from app.core.errors import DomainError
from app.core.events import Event
from app.core.task import TaskDefinition
from app.core.tools import ToolCall, ToolResult, ToolSpec
from app.services.file_service import FileService

ToolHandler = Callable[[TaskContext, ToolCall], ToolResult]


class ToolService:
    def __init__(self, specs: Dict[str, ToolSpec], handlers: Dict[str, ToolHandler], storage: Any):
        self.specs = specs
        self.handlers = handlers
        self.storage = storage
        self.knowledge_backend = None

    @classmethod
    def default(cls, root: Path, knowledge: Any) -> "ToolService":
        from app.services.fakes import FakeStorage

        storage = FakeStorage(root) if not hasattr(root, "append_event") else root
        file_service = FileService(storage)
        specs = build_default_tool_specs()

        def material_read(context: TaskContext, call: ToolCall) -> ToolResult:
            material_id = call.arguments.get("material_id")
            return ToolResult(call_id=call.id, status="succeeded", summary="material summary loaded", data={"material_id": material_id, "summary": "材料摘要占位，不泄露完整原文。"})

        def material_parse(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="materials parsed", data={"materials": context.source_materials})

        def knowledge_retrieve(context: TaskContext, call: ToolCall) -> ToolResult:
            result = knowledge.retrieve(call.arguments.get("query", context.goal), call.arguments.get("scope"))
            return ToolResult(call_id=call.id, status="succeeded", summary="knowledge retrieved", data=result)

        def artifact_write(context: TaskContext, call: ToolCall) -> ToolResult:
            artifact = file_service.write_artifact(
                task_id=context.task_id,
                name=call.arguments["name"],
                content=call.arguments.get("content", ""),
                created_by=call.agent_role,
            )
            return ToolResult(call_id=call.id, status="succeeded", summary=f"artifact {artifact.name} written", artifacts=[artifact], data={"artifact_id": artifact.artifact_id, "version": artifact.version})

        def artifact_read(context: TaskContext, call: ToolCall) -> ToolResult:
            artifact = file_service.read_artifact(call.arguments["artifact_id"])
            return ToolResult(call_id=call.id, status="succeeded", summary=f"artifact {artifact.name} read", artifacts=[artifact], data={"content": artifact.content})

        def artifact_backup(context: TaskContext, call: ToolCall) -> ToolResult:
            backup = file_service.backup_artifact(call.arguments["artifact_id"])
            return ToolResult(call_id=call.id, status="succeeded", summary="artifact backup created", data=backup)

        def format_validate(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="format validated", data={"passed": True, "violations": []})

        def diff_extract_rules(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="candidate rules extracted", data={"candidates": []})

        def event_emit(context: TaskContext, call: ToolCall) -> ToolResult:
            return ToolResult(call_id=call.id, status="succeeded", summary="event accepted", data={"event_type": call.arguments.get("type")})

        handlers = {
            "material.read": material_read,
            "material.parse": material_parse,
            "knowledge.retrieve": knowledge_retrieve,
            "artifact.write": artifact_write,
            "artifact.read": artifact_read,
            "artifact.backup": artifact_backup,
            "format.validate": format_validate,
            "diff.extract_rules": diff_extract_rules,
            "event.emit": event_emit,
        }
        service = cls(specs=specs, handlers=handlers, storage=storage)
        service.knowledge_backend = knowledge
        return service

    def invoke(self, definition: TaskDefinition, context: TaskContext, call: ToolCall) -> ToolResult:
        spec = self.specs.get(call.tool_name)
        if not spec:
            return ToolResult(call_id=call.id, status="failed", error=DomainError("tool.unknown", f"Unknown tool: {call.tool_name}"))
        if not definition.tool_policy.is_allowed(call.agent_role, call.step_id, call.tool_name):
            result = ToolResult(call_id=call.id, status="denied", error=DomainError("tool.denied", f"{call.agent_role} cannot call {call.tool_name} in {call.step_id}"))
            self._emit_tool_event(context.task_id, call, "tool.call.denied", result)
            return result

        self._emit_tool_event(context.task_id, call, "tool.call.started", None)
        try:
            result = self.handlers[call.tool_name](context, call)
        except Exception as exc:  # pragma: no cover - defensive wrapper
            result = ToolResult(call_id=call.id, status="failed", error=DomainError("tool.failed", str(exc)))
        event_type = "tool.call.completed" if result.status == "succeeded" else "tool.call.failed"
        self._emit_tool_event(context.task_id, call, event_type, result)
        return result

    def _emit_tool_event(self, task_id: str, call: ToolCall, event_type: str, result: ToolResult | None) -> None:
        if not self.storage:
            return
        payload = {"tool_name": call.tool_name, "step_id": call.step_id, "role": call.agent_role, "summary": result.summary if result else "started"}
        if result and result.artifacts:
            payload["artifact_ids"] = [artifact.artifact_id for artifact in result.artifacts]
        self.storage.append_event(Event(task_id=task_id, type=event_type, role=call.agent_role, status=result.status if result else "started", payload=payload))


def build_default_tool_specs() -> Dict[str, ToolSpec]:
    schemas = {"type": "object", "additionalProperties": True}
    return {
        "material.read": ToolSpec("material.read", "1.0", "读取用户上传材料摘要或授权片段", schemas, schemas, "read", ["material:read"]),
        "material.parse": ToolSpec("material.parse", "1.0", "将上传材料解析为结构化材料包", schemas, schemas, "read", ["material:read"]),
        "knowledge.retrieve": ToolSpec("knowledge.retrieve", "1.0", "按任务目标检索 GBrain 或本地知识快照", schemas, schemas, "read", ["knowledge:read"]),
        "artifact.write": ToolSpec("artifact.write", "1.0", "写 Markdown 产物并记录版本", schemas, schemas, "write", ["artifact:write"], event_semantics="Must emit tool.call.started and tool.call.completed/failed/denied."),
        "artifact.read": ToolSpec("artifact.read", "1.0", "读取已生成产物供审查或 Diff 使用", schemas, schemas, "read", ["artifact:read"]),
        "artifact.backup": ToolSpec("artifact.backup", "1.0", "用户编辑或重写前备份旧版本", schemas, schemas, "write", ["artifact:write"], event_semantics="Must emit tool.call.started and tool.call.completed/failed/denied."),
        "format.validate": ToolSpec("format.validate", "1.0", "校验操作手册格式红线或 PRD 结构要求", schemas, schemas, "none", []),
        "diff.extract_rules": ToolSpec("diff.extract_rules", "1.0", "从终稿变化中生成候选法则，不直接入库", schemas, schemas, "write", ["rules:candidate"], event_semantics="Writes candidates only; never approved rules."),
        "event.emit": ToolSpec("event.emit", "1.0", "统一输出结构化事件，禁止日志协议替代", schemas, schemas, "write", ["event:write"]),
    }
