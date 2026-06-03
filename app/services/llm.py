"""Real LLM implementation using OpenAI compatible API."""
import json
import time
import urllib.request
from typing import Any, Callable, Dict, Optional, Tuple, List
from urllib.parse import urlparse
from uuid import uuid4

from app.core.ports import LLMResult

TelemetryCallback = Callable[[str, Dict[str, Any]], None]


class OpenAILLM:
    WRITER_MAX_TOKENS = 24000
    DEFAULT_MAX_TOKENS = 4096

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _host(self) -> str:
        return urlparse(self.base_url).netloc or self.base_url

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, int((time.monotonic() - started_at) * 1000))

    @staticmethod
    def _emit(telemetry: Optional[TelemetryCallback], event_type: str, payload: Dict[str, Any]) -> None:
        if telemetry:
            telemetry(event_type, payload)

    @classmethod
    def _max_tokens_for_role(cls, role: str) -> int:
        return cls.WRITER_MAX_TOKENS if role.lower() == "writer" else cls.DEFAULT_MAX_TOKENS

    def _build_prompts(self, role: str, prompt: str, context: Dict[str, Any], is_stream: bool = False) -> Tuple[str, List[Dict[str, str]], str]:
        import os
        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        
        role_map = {
            "pm": "资深产品经理 (PM)，负责梳理业务目标、主业务流程、核心功能需求，编写 PRD 的核心部分。",
            "tech": "资深技术专家 (Tech)，负责从系统边界、数据流、一致性、性能瓶颈、限流熔断、异常降级等角度挑战产品设计，指出潜在的架构与技术风险。",
            "qa": "资深质量保证专家 (QA)，负责从异常路径、边界条件、并发安全、接口超时等异常场景挑战方案，设计严格的验收标准与测试要点。",
            "writer": "技术文档专家 (Writer)，负责整合前序意见编写 PRD 或操作手册。要求：结构高度凝练，一级/二级标题总数控制在 5~7 个核心章节以内，将零碎信息合并为子段落或表格，严禁生成十几个扁平化同级标题。"
        }
        role_desc = role_map.get(role.lower(), f"专业协作角色: {role}")
        
        # Sticky Latch: 始终把不可变规则放在 System Prompt 前方
        workspace_root = os.getcwd()
        memory_path = os.path.join(workspace_root, "MEMORY.md")
        claude_path = os.path.join(workspace_root, "CLAUDE.md")
        
        fixed_context = ""
        for path, name in [(memory_path, "MEMORY.md"), (claude_path, "CLAUDE.md")]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            fixed_context += f"\n【{name}】\n{content}\n"
                except Exception:
                    pass

        system_prompt = f"你现在扮演的角色是: {role}。\n角色定位: {role_desc}\n"
        if fixed_context:
            system_prompt += f"\n--- 全局系统锁定上下文 (Sticky Latch) ---\n{fixed_context}\n-----------------------------------\n"
            
        system_prompt += f"\n任务标题: {title}\n任务目标: {goal}"
        if is_stream and role.lower() != "writer":
            system_prompt += "\n【系统指令】请保持极度精简、一针见血。输出字数必须严格控制在 100~300 字以内，严禁任何废话与长篇大论。"

        history_str = ""
        # Context Compaction & Microcompact: 折叠超长历史输出
        for msg in context.get("round_history", []):
            content = msg.get("content", "")
            if len(content) > 3000:
                # 超过阈值，截取头 1500 和尾 500
                content = content[:1500] + "\n\n... [长文本已触发 Microcompact 折叠] ...\n\n" + content[-500:]
            history_str += f"【{msg['role']}】:\n{content}\n\n"

        # 始终把变化的动态数据放在末尾 User Prompt
        messages = [{"role": "system", "content": system_prompt}]
        if history_str:
            messages.append({"role": "user", "content": f"以下是先前的协作讨论历史：\n\n{history_str}请根据上述历史背景继续你的发言。"})
        messages.append({"role": "user", "content": prompt or f"请开始处理任务: {title}"})

        anthropic_user_prompt = ""
        if history_str:
            anthropic_user_prompt += f"以下是先前的协作讨论历史：\n\n{history_str}请根据上述历史背景继续你的发言。\n\n"
        anthropic_user_prompt += prompt or f"请开始处理任务: {title}"

        return system_prompt, messages, anthropic_user_prompt

    def invoke(self, role: str, prompt: str, context: Dict[str, Any]) -> LLMResult:
        model = context.get("model") or "gpt-5.4"
        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        
        system_prompt, messages, anthropic_user_prompt = self._build_prompts(role, prompt, context, is_stream=False)
        user_prompt = prompt or f"请开始处理任务: {title}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        data = {
            "model": model,
            "messages": messages
        }
        
        url = f"{self.base_url}/chat/completions"
        req = urllib.request.Request(
            url, 
            data=json.dumps(data).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                content = result["choices"][0]["message"]["content"]
                return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal, "model": model})
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                error_msg = error_json.get("error", {}).get("message") or error_body
            except Exception:
                error_msg = str(e)
                
            if "不支持" in error_msg and "Api格式" in error_msg:
                anthropic_url = f"{self.base_url}/messages"
                anthropic_data = {
                    "model": model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}]
                }
                anthropic_headers = dict(headers)
                anthropic_headers["anthropic-version"] = "2023-06-01"
                req = urllib.request.Request(anthropic_url, data=json.dumps(anthropic_data).encode("utf-8"), headers=anthropic_headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        content = ""
                        for block in result.get("content", []):
                            if block.get("type") == "text":
                                content += block.get("text", "")
                        return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal, "model": model})
                except Exception as retry_e:
                    error_msg = f"Anthropic 格式调用也失败: {str(retry_e)}"

            if "Vip" in error_msg or "不存在" in error_msg or "失败" in error_msg or "不支持" in error_msg:
                data["model"] = "DeepSeek-V3-0324"
                req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        content = result["choices"][0]["message"]["content"]
                        return LLMResult(content=content, structured={"role": role, "title": title, "goal": goal, "model": "DeepSeek-V3-0324 (Fallback)"})
                except Exception:
                    pass

            return LLMResult(content=f"LLM 调用失败: {error_msg}", structured={"role": role, "error": error_msg, "model": model})
        except Exception as e:
            error_msg = f"LLM 调用失败: {str(e)}"
            return LLMResult(content=error_msg, structured={"role": role, "error": str(e), "model": model})

    def invoke_stream(self, role: str, prompt: str, context: Dict[str, Any], telemetry: Optional[TelemetryCallback] = None):
        model = context.get("model") or "gpt-5.4"
        title = context.get("title") or "未命名任务"
        goal = context.get("goal") or "无特定目标"
        
        system_prompt, messages, anthropic_user_prompt = self._build_prompts(role, prompt, context, is_stream=True)
        user_prompt = prompt or f"请开始处理任务: {title}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        data = {
            "model": model,
            "messages": messages,
            "stream": True
        }
        
        import requests
        import io
        import urllib.error
        url = f"{self.base_url}/chat/completions"
        call_id = f"llm_{uuid4().hex[:12]}"
        started_at = time.monotonic()
        self._emit(telemetry, "llm.call.started", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "stream": True})
        try:
            with requests.post(url, json=data, headers=headers, stream=True, timeout=10) as response:
                self._emit(telemetry, "llm.call.headers_received", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "status_code": response.status_code, "ttfb_ms": self._duration_ms(started_at)})
                if response.status_code != 200:
                    raise urllib.error.HTTPError(url, response.status_code, "HTTP Error", headers, io.BytesIO(response.content))
                
                first_token_seen = False
                chunk_count = 0
                output_chars = 0
                chunk_gaps = []
                last_chunk_at = None
                for line in response.iter_lines():
                    if line:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    now = time.monotonic()
                                    if not first_token_seen:
                                        first_token_seen = True
                                        self._emit(telemetry, "llm.call.first_token", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "first_token_ms": self._duration_ms(started_at)})
                                    if last_chunk_at is not None:
                                        chunk_gaps.append(int((now - last_chunk_at) * 1000))
                                    last_chunk_at = now
                                    chunk_count += 1
                                    output_chars += len(content)
                                    yield content
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
                self._emit(telemetry, "llm.call.completed", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "duration_ms": self._duration_ms(started_at), "output_chars": output_chars, "chunk_count": chunk_count, "max_chunk_gap_ms": max(chunk_gaps) if chunk_gaps else 0, "avg_chunk_gap_ms": int(sum(chunk_gaps) / len(chunk_gaps)) if chunk_gaps else 0})
                return
        except urllib.error.HTTPError as e:
            self._emit(telemetry, "llm.call.failed", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "duration_ms": self._duration_ms(started_at), "status_code": getattr(e, "code", None), "error_type": "HTTPError"})
            try:
                error_body = e.read().decode("utf-8")
                error_json = json.loads(error_body)
                error_msg = error_json.get("error", {}).get("message") or error_body
            except Exception:
                error_msg = str(e)
                
            if "不支持" in error_msg and "Api格式" in error_msg:
                anthropic_url = f"{self.base_url}/messages"
                anthropic_call_id = f"llm_{uuid4().hex[:12]}"
                anthropic_started_at = time.monotonic()
                self._emit(telemetry, "llm.call.started", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "stream": True})
                anthropic_data = {
                    "model": model,
                    "max_tokens": self._max_tokens_for_role(role),
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": anthropic_user_prompt}],
                    "stream": True
                }
                anthropic_headers = dict(headers)
                anthropic_headers["anthropic-version"] = "2023-06-01"
                try:
                    with requests.post(anthropic_url, json=anthropic_data, headers=anthropic_headers, stream=True, timeout=120) as response:
                        self._emit(telemetry, "llm.call.headers_received", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "status_code": response.status_code, "ttfb_ms": self._duration_ms(anthropic_started_at)})
                        if response.status_code != 200:
                            raise Exception(response.text)
                        first_token_seen = False
                        chunk_count = 0
                        output_chars = 0
                        chunk_gaps = []
                        last_chunk_at = None
                        for line in response.iter_lines():
                            if line:
                                line = line.decode("utf-8").strip()
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    try:
                                        chunk = json.loads(data_str)
                                        if chunk.get("type") == "content_block_delta":
                                            delta = chunk.get("delta", {})
                                            content = delta.get("text", "") or delta.get("thinking", "")
                                            if content:
                                                now = time.monotonic()
                                                if not first_token_seen:
                                                    first_token_seen = True
                                                    self._emit(telemetry, "llm.call.first_token", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "first_token_ms": self._duration_ms(anthropic_started_at)})
                                                if last_chunk_at is not None:
                                                    chunk_gaps.append(int((now - last_chunk_at) * 1000))
                                                last_chunk_at = now
                                                chunk_count += 1
                                                output_chars += len(content)
                                                yield content
                                    except json.JSONDecodeError:
                                        pass
                        self._emit(telemetry, "llm.call.completed", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "duration_ms": self._duration_ms(anthropic_started_at), "output_chars": output_chars, "chunk_count": chunk_count, "max_chunk_gap_ms": max(chunk_gaps) if chunk_gaps else 0, "avg_chunk_gap_ms": int(sum(chunk_gaps) / len(chunk_gaps)) if chunk_gaps else 0})
                    return
                except Exception as retry_e:
                    self._emit(telemetry, "llm.call.failed", {"call_id": anthropic_call_id, "model": model, "base_url_host": self._host(), "provider_format": "anthropic", "duration_ms": self._duration_ms(anthropic_started_at), "error_type": type(retry_e).__name__})
                    error_msg = f"Anthropic 格式调用也失败: {str(retry_e)}"

            if "Vip" in error_msg or "不存在" in error_msg or "失败" in error_msg or "不支持" in error_msg:
                yield {"type": "event", "name": "model.fallback", "message": "主模型响应超时，已无缝切换至备用模型 (DeepSeek-V3)"}
                data["model"] = "DeepSeek-V3-0324"
                fallback_call_id = f"llm_{uuid4().hex[:12]}"
                fallback_started_at = time.monotonic()
                self._emit(telemetry, "llm.call.fallback", {"from_model": model, "to_model": "DeepSeek-V3-0324", "base_url_host": self._host(), "reason_type": "provider_error"})
                self._emit(telemetry, "llm.call.started", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "stream": True})
                try:
                    with requests.post(url, json=data, headers=headers, stream=True, timeout=120) as response:
                        self._emit(telemetry, "llm.call.headers_received", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "status_code": response.status_code, "ttfb_ms": self._duration_ms(fallback_started_at)})
                        if response.status_code == 200:
                            first_token_seen = False
                            chunk_count = 0
                            output_chars = 0
                            chunk_gaps = []
                            last_chunk_at = None
                            for line in response.iter_lines():
                                if line:
                                    line = line.decode("utf-8").strip()
                                    if line.startswith("data: "):
                                        data_str = line[6:]
                                        if data_str == "[DONE]":
                                            break
                                        try:
                                            chunk = json.loads(data_str)
                                            delta = chunk["choices"][0].get("delta", {})
                                            content = delta.get("content", "")
                                            if content:
                                                now = time.monotonic()
                                                if not first_token_seen:
                                                    first_token_seen = True
                                                    self._emit(telemetry, "llm.call.first_token", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "first_token_ms": self._duration_ms(fallback_started_at)})
                                                if last_chunk_at is not None:
                                                    chunk_gaps.append(int((now - last_chunk_at) * 1000))
                                                last_chunk_at = now
                                                chunk_count += 1
                                                output_chars += len(content)
                                                yield content
                                        except (json.JSONDecodeError, KeyError, IndexError):
                                            pass
                            self._emit(telemetry, "llm.call.completed", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "duration_ms": self._duration_ms(fallback_started_at), "output_chars": output_chars, "chunk_count": chunk_count, "max_chunk_gap_ms": max(chunk_gaps) if chunk_gaps else 0, "avg_chunk_gap_ms": int(sum(chunk_gaps) / len(chunk_gaps)) if chunk_gaps else 0})
                            return
                        self._emit(telemetry, "llm.call.failed", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "duration_ms": self._duration_ms(fallback_started_at), "status_code": response.status_code, "error_type": "HTTPStatus"})
                except Exception:
                    self._emit(telemetry, "llm.call.failed", {"call_id": fallback_call_id, "model": "DeepSeek-V3-0324", "base_url_host": self._host(), "provider_format": "chat_fallback", "duration_ms": self._duration_ms(fallback_started_at), "error_type": "Exception"})

            yield f"\n\nLLM 调用失败: {error_msg}"
        except Exception as e:
            self._emit(telemetry, "llm.call.failed", {"call_id": call_id, "model": model, "base_url_host": self._host(), "provider_format": "chat", "duration_ms": self._duration_ms(started_at), "error_type": type(e).__name__})
            yield f"\n\nLLM 调用失败: {str(e)}"
