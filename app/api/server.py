"""FastAPI surface for the Phase 1 PM-Agent backend and EvoLoop frontend."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks, Body
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
except Exception:  # pragma: no cover - importable without runtime web deps
    FastAPI = None  # type: ignore
    File = None  # type: ignore
    HTTPException = Exception  # type: ignore
    UploadFile = object  # type: ignore
    BackgroundTasks = object  # type: ignore
    CORSMiddleware = None  # type: ignore
    StreamingResponse = None  # type: ignore
    class DummyBody:
        def __call__(self, *args, **kwargs):
            return None
    Body = DummyBody()

from app.api.schemas import CreateTaskRequest, DecisionRequest, MaterialUploadResponse
from app.services.fakes import FakeLLM, FakeStorage
from app.services.gbrain_service import GBrainKnowledge
from app.services.task_service import TaskService
from app.services.tool_service import ToolService
from app.services.llm import OpenAILLM
from app.workflows.definitions import build_task_registry
from app.workflows.engine import WorkflowEngine
from app.core.events import EventBus

global_event_bus = EventBus()


AGENT_META = {
    "PM": {"agent": "PM Agent", "role": "主导中", "avatar": "PM", "color": "#7c3aed"},
    "Tech": {"agent": "Tech Agent", "role": "挑战中", "avatar": "T", "color": "#2563eb"},
    "QA": {"agent": "QA Agent", "role": "评估中", "avatar": "QA", "color": "#dc2626"},
    "Reviewer": {"agent": "Reviewer", "role": "门禁中", "avatar": "R", "color": "#d97706"},
    "Writer": {"agent": "Writer", "role": "写作中", "avatar": "W", "color": "#16a34a"},
    "SYSTEM": {"agent": "Workflow", "role": "执行中", "avatar": "WF", "color": "#6b7280"},
}


def build_default_task_service(root: Path | None = None) -> TaskService:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    storage = FakeStorage(root or Path(tempfile.gettempdir()) / "manual-agent-phase1", event_bus=global_event_bus)
    project_root = Path(__file__).parent.parent.parent
    tool_service = ToolService.default(root=storage, knowledge=GBrainKnowledge(str(project_root)))
    
    api_key = os.getenv("API_KEY") or os.getenv("CRS_OAI_KEY") or ""
    base_url = os.getenv("BASE_URL") or "https://api.openai.com/v1"
    llm = OpenAILLM(api_key=api_key, base_url=base_url)
    
    engine = WorkflowEngine(tool_service=tool_service, llm=llm, storage=storage)
    return TaskService(registry=build_task_registry(), engine=engine, storage=storage)


def create_app(task_service: TaskService | None = None):
    if FastAPI is None:
        raise RuntimeError("fastapi is required to create the HTTP app")
    service = task_service or build_default_task_service()
    app = FastAPI(title="PM-Agent Platform API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:4000",
            "http://127.0.0.1:4000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8080",
            "http://127.0.0.1:8080",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "service": "pm-agent-backend", "version": "0.1.0"}

    @app.get("/api/knowledge/health")
    def knowledge_health() -> Dict[str, Any]:
        knowledge = getattr(service.engine.tool_service, "knowledge_backend", None)
        data = knowledge.retrieve("WorkflowEngine TaskDefinition ToolService") if knowledge else {"degraded": True, "items": [], "error": "knowledge backend unavailable"}
        return {
            "status": "degraded" if data.get("degraded") else "ok",
            "items": len(data.get("items", [])),
            "error": data.get("error"),
        }

    @app.post("/api/tasks")
    def create_task(request: CreateTaskRequest) -> Dict[str, Any]:
        payload = request.model_dump(exclude_none=True) if hasattr(request, "model_dump") else request.dict(exclude_none=True)  # pydantic v1 fallback
        normalized = _normalize_create_payload(payload)
        try:
            task = service.create_task(normalized.pop("type"), normalized)
            
            def update_title_async():
                prompt = (
                    payload.get("prompt")
                    or payload.get("goal")
                    or payload.get("business_goal")
                    or payload.get("business_intent")
                    or ""
                ).strip()
                if not prompt: return
                res = service.engine.llm.invoke("System", f"请为以下任务目标取一个精简的名字（不超过10个字），直接输出名字本身，不要带标点和前缀：\n{prompt[:500]}", {})
                if res.content and not "失败" in res.content:
                    new_title = res.content.strip(' "”\'\n').strip()
                    if new_title:
                        t = service.get_task(task.task_id)
                        t.context.title = new_title
                        service.storage.save_task(t)

            threading.Thread(target=update_title_async, daemon=True).start()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"task_id": task.task_id, "taskId": task.task_id, "id": task.task_id, "status": task.status.value}

    @app.get("/api/tasks")
    def list_tasks() -> Dict[str, Any]:
        return {"tasks": [_frontend_task(item) for item in service.storage.list_tasks(service.registry) if not getattr(item, "is_deleted", False)]}

    @app.get("/api/work-items")
    def list_work_items() -> Dict[str, Any]:
        tasks = [
            item for item in service.storage.list_tasks(service.registry)
            if not getattr(item, "is_deleted", False)
        ]
        return {
            "work_items": [
                service.get_work_item(task.task_id).to_dict()
                for task in tasks
            ]
        }

    @app.get("/api/work-items/{work_id}")
    def get_work_item(work_id: str) -> Dict[str, Any]:
        _load_task_or_404(service, work_id)
        return service.get_work_item(work_id).to_dict()

    @app.get("/api/work-items/{work_id}/product-context")
    def get_work_item_product_context(work_id: str) -> Dict[str, Any]:
        _load_task_or_404(service, work_id)
        return service.get_product_context(work_id).to_dict()

    @app.get("/api/work-items/{work_id}/artifact-graph")
    def get_work_item_artifact_graph(work_id: str) -> Dict[str, Any]:
        _load_task_or_404(service, work_id)
        return service.get_artifact_graph(work_id).to_dict()

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str) -> Dict[str, Any]:
        task = _load_task_or_404(service, task_id)
        return _frontend_task(task)

    @app.post("/api/tasks/{task_id}/run")
    def run_task(task_id: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        task = _load_task_or_404(service, task_id)
        background_tasks.add_task(service.run_task, task_id)
        return {"task_id": task.task_id, "taskId": task.task_id, "status": task.status.value, "waiting_step_id": task.waiting_step_id}

    @app.post("/api/tasks/{task_id}/interrupt")
    def interrupt_task(task_id: str) -> Dict[str, Any]:
        _load_task_or_404(service, task_id)
        task = service.cancel_task(task_id)
        return {"task_id": task.task_id, "taskId": task.task_id, "status": task.status.value}

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: str) -> Dict[str, Any]:
        task = _load_task_or_404(service, task_id)
        service.delete_task(task_id)
        return {"id": task.task_id, "status": "deleted"}

    @app.get("/api/tasks/{task_id}/events")
    async def get_events(task_id: str):
        _load_task_or_404(service, task_id)

        async def stream():
            import asyncio
            import queue
            for event in service.storage.read_events(task_id):
                data = event.to_dict()
                data["frontend_message"] = _event_to_frontend_message(data)
                yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                
            if hasattr(service.storage, "event_bus") and service.storage.event_bus:
                q = service.storage.event_bus.subscribe(task_id)
                try:
                    while True:
                        try:
                            event = q.get_nowait()
                            data = event.to_dict()
                            data["frontend_message"] = _event_to_frontend_message(data)
                            yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                            if event.type in {"task.completed", "task.cancelled", "task.failed"}:
                                break
                        except queue.Empty:
                            await asyncio.sleep(0.1)
                finally:
                    service.storage.event_bus.unsubscribe(task_id, q)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/tasks/{task_id}/messages")
    def get_task_messages(task_id: str) -> Dict[str, Any]:
        _load_task_or_404(service, task_id)
        messages = [_event_to_frontend_message(event.to_dict()) for event in service.storage.read_events(task_id)]
        return {"messages": [message for message in messages if message and message.get("type") != "typing"]}

    @app.post("/api/tasks/{task_id}/decisions")
    def apply_decision(task_id: str, request: DecisionRequest) -> Dict[str, Any]:
        _load_task_or_404(service, task_id)
        
        import re
        frustration_patterns = [r'(?i)wtf', r'(?i)not working', r'(?i)fails again', r'(?i)fuck', r'(?i)糟糕', r'(?i)根本不行', r'(?i)又失败了']
        user_text = request.decision or ""
        if any(re.search(p, user_text) for p in frustration_patterns):
            request.decision = user_text + "\n[System: 用户情绪受挫。请暂停盲目重试，微调沟通姿态，先安抚并提供 step-by-step 的澄清引导，找出卡点所在。]"
            
        task = service.apply_decision(
            task_id,
            request.decision,
            request.selected_option,
            request.quoted_selections,
        )
        return {"task_id": task.task_id, "taskId": task.task_id, "status": task.status.value}

    @app.get("/api/tasks/{task_id}/artifacts")
    def list_artifacts(task_id: str) -> Dict[str, Any]:
        _load_task_or_404(service, task_id)
        return {"artifacts": [artifact.to_dict() for artifact in service.storage.list_artifacts(task_id)]}

    @app.get("/api/tasks/{task_id}/document")
    def get_task_document(task_id: str) -> Dict[str, Any]:
        task = _load_task_or_404(service, task_id)
        artifacts = service.storage.list_artifacts(task_id)
        artifact = artifacts[-1] if artifacts else None
        if not artifact:
            content = f"# {task.context.title}\n\n任务已创建，文档产物将在 Workflow 完成后生成。\n"
            return {"task_id": task_id, "taskId": task_id, "artifact_id": None, "artifactId": None, "content": content, "title": task.context.title}
        full = service.storage.read_artifact(artifact.artifact_id)
        return {
            "task_id": task_id,
            "taskId": task_id,
            "artifact_id": full.artifact_id,
            "artifactId": full.artifact_id,
            "name": full.name,
            "version": full.version,
            "title": task.context.title,
            "content": full.content or "",
        }

    @app.put("/api/tasks/{task_id}/document")
    def update_task_document(task_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        task = _load_task_or_404(service, task_id)
        artifacts = service.storage.list_artifacts(task_id)
        if not artifacts:
            name = task.definition.output_spec.get("primary_artifact", "document.md")
            artifact = service.storage.write_artifact(task_id, name, payload.get("content", ""), created_by="user")
        else:
            service.storage.backup_artifact(artifacts[-1].artifact_id)
            artifact = service.storage.update_artifact(artifacts[-1].artifact_id, payload.get("content", artifacts[-1].content or ""), updated_by="user")
        return {"artifact_id": artifact.artifact_id, "artifactId": artifact.artifact_id, "version": artifact.version, "content": artifact.content or ""}

    @app.get("/api/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str) -> Dict[str, Any]:
        try:
            return service.storage.read_artifact(artifact_id).to_dict(include_content=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="artifact not found") from exc

    @app.put("/api/artifacts/{artifact_id}")
    def update_artifact(artifact_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        try:
            service.storage.backup_artifact(artifact_id)
            updated = service.storage.update_artifact(artifact_id, payload.get("content", ""), updated_by="user")
            return updated.to_dict(include_content=True)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="artifact not found") from exc

    @app.post("/api/materials", response_model=MaterialUploadResponse)
    def upload_material(file: UploadFile = File(...)) -> MaterialUploadResponse:
        return MaterialUploadResponse(material_id=f"material_{uuid4().hex[:12]}", status="uploaded", summary=f"{file.filename} uploaded; full local path is not exposed.")

    @app.get("/api/knowledge")
    def list_knowledge() -> Dict[str, Any]:
        return {"items": _knowledge_items()}

    @app.post("/api/knowledge")
    def create_knowledge(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        item = {
            "id": f"kb_{uuid4().hex[:8]}",
            "type": payload.get("type", "doc"),
            "title": payload.get("title", "未命名知识"),
            "desc": payload.get("desc", "已提交到候选知识区，等待后续解析入库。"),
            "tags": payload.get("tags", []),
            "updated": "刚刚",
            "author": payload.get("author", "User"),
        }
        return item

    @app.get("/api/rules")
    def list_rules(status: str = "pending") -> Dict[str, Any]:
        return {"rules": [rule for rule in _rule_items() if rule["status"] == status]}

    @app.post("/api/rules/{rule_id}/approve")
    def approve_rule(rule_id: str, payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
        p = payload or {}
        content = p.get("content") or p.get("desc") or p.get("title")
        return {"id": rule_id, "status": "approved", "content": content}

    @app.post("/api/rules/{rule_id}/reject")
    def reject_rule(rule_id: str) -> Dict[str, Any]:
        return {"id": rule_id, "status": "rejected"}

    @app.get("/api/recycle")
    def list_recycle() -> Dict[str, Any]:
        tasks = service.storage.list_tasks(service.registry)
        deleted_tasks = [t for t in tasks if getattr(t, "is_deleted", False)]
        items = []
        for t in deleted_tasks:
            import os
            task_file = service.storage._task_dir(t.task_id) / "task.json"
            size = "N/A"
            if task_file.exists():
                size_kb = os.path.getsize(task_file) / 1024
                size = f"{size_kb:.1f} KB"
            items.append({
                "id": t.task_id,
                "name": t.context.title,
                "type": "task",
                "size": size,
                "deletedAt": _format_event_time(t.deleted_at) if getattr(t, "deleted_at", None) else "刚刚",
                "deletedBy": "User"
            })
        return {"items": items + _recycle_items()}

    @app.post("/api/recycle/{item_id}/restore")
    def restore_recycle(item_id: str) -> Dict[str, Any]:
        if item_id.startswith("trash_"):
            return {"id": item_id, "status": "restored"}
        try:
            service.restore_task(item_id)
        except Exception:
            raise HTTPException(status_code=404, detail="task not found")
        return {"id": item_id, "status": "restored"}

    @app.delete("/api/recycle/{item_id}")
    def delete_recycle(item_id: str) -> Dict[str, Any]:
        if item_id.startswith("trash_"):
            return {"id": item_id, "status": "deleted"}
        service.permanent_delete_task(item_id)
        return {"id": item_id, "status": "deleted"}

    @app.get("/api/conversations/recent")
    def recent_conversations() -> Dict[str, Any]:
        import os
        from datetime import datetime, date
        tasks_data = []
        today_date = date.today()

        for task in service.storage.list_tasks(service.registry):
            if getattr(task, "is_deleted", False):
                continue
            
            task_dir = service.storage.root / "tasks" / task.task_id
            task_file = task_dir / "task.json"
            events_file = task_dir / "events.jsonl"
            
            if task_file.exists():
                stat = os.stat(task_file)
                # 基础时间：任务创建时间
                last_activity = getattr(stat, 'st_birthtime', stat.st_ctime)
                
                # 检查最新对话时间
                if events_file.exists():
                    last_activity = max(last_activity, os.path.getmtime(events_file))
                
                # 检查最新文档改动时间
                artifacts = service.storage.list_artifacts(task.task_id)
                if artifacts:
                    art_file = service.storage._artifacts_dir() / f"{artifacts[-1].artifact_id}.json"
                    if art_file.exists():
                        last_activity = max(last_activity, os.path.getmtime(art_file))
                
                created_dt = datetime.fromtimestamp(last_activity)
                delta_days = (today_date - created_dt.date()).days
                
                if delta_days == 0:
                    time_label = created_dt.strftime("%H:%M")
                    group = "today"
                elif delta_days == 1:
                    time_label = "1天前"
                    group = "yesterday"
                else:
                    time_label = f"{delta_days}天前"
                    group = "older"
                    
                sort_key = last_activity
            else:
                time_label = "刚刚"
                group = "today"
                sort_key = 0
                
            tasks_data.append((sort_key, task, time_label, group))
            
        # 按最后活跃时间倒序排列
        tasks_data.sort(key=lambda x: x[0], reverse=True)
        
        grouped = {"today": [], "yesterday": [], "older": []}
        for _, task, time_label, group in tasks_data:
            grouped[group].append({
                "id": task.task_id,
                "label": task.context.title,
                "time": time_label,
                "active": False
            })
        return grouped

    return app


def _normalize_create_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    prompt = (payload.get("prompt") or payload.get("goal") or payload.get("business_goal") or "").strip()
    
    import re
    frustration_patterns = [r'(?i)wtf', r'(?i)not working', r'(?i)fails again', r'(?i)fuck', r'(?i)糟糕', r'(?i)根本不行', r'(?i)又失败了']
    if any(re.search(p, prompt) for p in frustration_patterns):
        prompt += "\n[System: 用户情绪受挫。请微调沟通姿态，先安抚并提供 step-by-step 的澄清引导，找出卡点所在。]"
        if "prompt" in payload: payload["prompt"] = prompt
        elif "goal" in payload: payload["goal"] = prompt
        elif "business_goal" in payload: payload["business_goal"] = prompt

    task_type = payload.get("type") or _infer_task_type(prompt)
    normalized = dict(payload)
    normalized["type"] = task_type
    normalized["username"] = payload.get("username") or "frontend"
    if task_type == "manual":
        normalized["module_name"] = payload.get("module_name") or payload.get("title") or _title_from_prompt(prompt, "操作手册")
        normalized["goal"] = payload.get("goal") or prompt or f"生成{normalized['module_name']}操作手册"
    elif task_type == "spec_to_agent":
        normalized["business_intent"] = (
            payload.get("business_intent")
            or payload.get("prompt")
            or payload.get("goal")
            or payload.get("business_goal")
            or ""
        )
    elif task_type == "acceptance_review":
        normalized["machine_spec"] = payload.get("machine_spec") or ""
        normalized["acceptance_protocol"] = payload.get("acceptance_protocol") or ""
        normalized["implementation_summary"] = payload.get("implementation_summary") or ""
        normalized["diff"] = payload.get("diff") or ""
    else:
        normalized["feature"] = payload.get("feature") or payload.get("title") or _title_from_prompt(prompt, "PRD")
        normalized["business_goal"] = payload.get("business_goal") or payload.get("goal") or prompt or f"梳理{normalized['feature']}业务诉求"
    normalized.setdefault("title", normalized.get("feature") or normalized.get("module_name"))
    return normalized


def _infer_task_type(prompt: str) -> str:
    if any(keyword in prompt.lower() for keyword in ["manual", "操作手册", "手册", "教程"]):
        return "manual"
    return "prd"


def _title_from_prompt(prompt: str, fallback: str) -> str:
    clean = " ".join(prompt.split())
    if not clean:
        return fallback
    return clean[:32]


def _load_task_or_404(service: TaskService, task_id: str):
    try:
        return service.get_task(task_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="task not found") from exc


def _frontend_task(task: Any) -> Dict[str, Any]:
    status_map = {"created": "pending", "running": "running", "waiting_for_user": "review", "completed": "done", "failed": "review", "blocked": "review", "cancelled": "done"}
    agents = "PM + Tech + QA" if task.definition.type == "prd" else "PM + Tech + QA + Writer"
    knowledge_state = (getattr(task.context, "degradation_state", {}) or {}).get("knowledge", {})
    return {
        "id": task.task_id,
        "task_id": task.task_id,
        "title": task.context.title,
        "type": task.definition.type,
        "status": status_map.get(task.status.value, "pending"),
        "raw_status": task.status.value,
        "agent": agents,
        "priority": "medium",
        "updated": "刚刚",
        "waiting_step_id": task.waiting_step_id,
        "knowledge_status": {
            "state": "error" if knowledge_state.get("degraded") else ("ready" if knowledge_state.get("items", 0) > 0 else "no_results"),
            "degraded": bool(knowledge_state.get("degraded")),
            "error": knowledge_state.get("error"),
            "items": knowledge_state.get("items", 0),
            "preview": knowledge_state.get("preview", []),
        },
    }


def _event_to_frontend_message(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    role = event.get("role") or "SYSTEM"
    meta = AGENT_META.get(role, AGENT_META["SYSTEM"])
    event_type = event.get("type")
    payload = event.get("payload") or {}
    
    valid_frontend_events = {
        "workflow.step.started",
        "agent.message.chunk",
        "agent.message.completed",
        "arbitration.requested",
        "artifact.created",
        "task.completed",
        "task.cancelled",
        "task.failed",
        "tool.call.denied",
        "model.fallback",
    }
    
    if event_type not in valid_frontend_events:
        return None

    content = payload.get("summary")
    highlights = None
    step_id = payload.get("step_id") or event.get("id")
    
    if event_type == "workflow.step.started":
        if payload.get("step_type") != "agent":
            return None
        return {**meta, "id": step_id, "type": "typing", "content": "深度思考中...", "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}
    elif event_type == "agent.message.chunk":
        return {**meta, "id": step_id, "type": "chunk", "content": payload.get("chunk", ""), "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}
    elif event_type == "model.fallback":
        return {"id": event.get("id"), "type": "toast", "content": payload.get("message"), "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}
    elif event_type == "agent.message.completed":
        content = payload.get("content") or payload.get("summary") or "Agent 已完成本轮输出。"
    elif event_type == "arbitration.requested":
        dispute = payload.get("dispute_package", {})
        content = dispute.get("decision_needed") or "需要用户裁决后继续。"
        highlights = {"label": dispute.get("title", "需要裁决"), "color": meta["color"], "items": [item.get("pm_position") or item.get("label") for item in dispute.get("options", [])]}
    elif event_type == "artifact.created":
        content = f"文档产物已生成：{payload.get('name')}"
    elif event_type == "task.completed":
        content = "任务已完成，最终 Markdown 文档已准备好。"
    elif event_type == "task.cancelled":
        content = "任务已暂停/取消。"
    elif event_type == "task.failed":
        content = "任务执行失败。"
    elif event_type == "tool.call.denied":
        content = payload.get("summary") or f"工具调用被拒绝：{payload.get('tool_name')}"
        
    if not content and event_type != "model.fallback":
        return None
    return {**meta, "id": step_id, "content": content, "highlights": highlights, "isFinal": event_type == "task.completed", "time": _format_event_time(event.get("created_at")), "created_at": event.get("created_at")}


def _format_event_time(value: Optional[str]) -> str:
    if not value or "T" not in value:
        return "刚刚"
    return value.split("T", 1)[1][:5]


def _knowledge_items() -> List[Dict[str, Any]]:
    return [
        {"id": "kb_001", "type": "doc", "title": "PM-Agent 后端架构契约", "desc": "TaskDefinition、WorkflowEngine、ToolService 与结构化事件协议。", "tags": ["架构", "后端"], "updated": "刚刚", "author": "Codex"},
        {"id": "kb_002", "type": "rule", "title": "Agent 必须通过 ToolPolicy 调用能力", "desc": "禁止 Agent 直接读写文件、任意 shell、任意网络和绕过 TaskContext。", "tags": ["规则", "安全"], "updated": "刚刚", "author": "Reviewer"},
        {"id": "kb_003", "type": "template", "title": "PRD Markdown 输出模板", "desc": "结构化 PRD 初稿模板，后续由 Writer 产物生成补全。", "tags": ["模板", "PRD"], "updated": "刚刚", "author": "PM Agent"},
    ]


def _rule_items() -> List[Dict[str, Any]]:
    return [
        {"id": "R-0021", "title": "技术方案必须包含熔断降级策略", "desc": "Diff Agent 候选法则示例，等待人工批准后才能入可信区。", "source": "PRD 最小工作流", "sourceId": "task_demo", "extractedAt": "刚刚", "confidence": 94, "status": "pending"},
        {"id": "R-0017", "title": "文档标题需包含版本号", "source": "历史任务", "approvedAt": "3 天前", "confidence": 88, "status": "approved"},
        {"id": "R-0015", "title": "所有任务默认启用深度思考模式", "source": "历史任务", "rejectedAt": "1 周前", "confidence": 60, "status": "rejected"},
    ]


def _recycle_items() -> List[Dict[str, Any]]:
    return [
        {"id": "trash_001", "name": "旧版产品需求文档 v1.0.md", "type": "doc", "size": "32 KB", "deletedAt": "今天", "deletedBy": "PM Agent"},
    ]


app = create_app() if FastAPI is not None else None
