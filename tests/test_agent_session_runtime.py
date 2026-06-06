import unittest

from app.core.ports import LLMResult


def make_tool_runtime_context():
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from app.core.context import TaskContext
    from app.core.task import TaskDefinition, WorkflowSpec
    from app.services.fakes import FakeKnowledge, FakeStorage
    from app.services.tool_service import ToolService
    from app.workflows.policies import build_default_tool_policy

    temp = TemporaryDirectory()
    storage = FakeStorage(Path(temp.name))
    context = TaskContext(
        task_id="task_tool",
        task_type="spec_to_agent",
        username="alice",
        title="Tool Test",
        goal="Use tool",
    )
    definition = TaskDefinition(
        type="spec_to_agent",
        display_name="Spec To Agent",
        input_schema={},
        workflow=WorkflowSpec(name="x", version="1", steps=[]),
        tool_policy=build_default_tool_policy("spec_to_agent"),
    )
    tool_service = ToolService.default(root=storage, knowledge=FakeKnowledge())
    return temp, definition, context, tool_service


class AgentSessionContractTests(unittest.TestCase):
    def test_agent_session_defaults_and_trace_append(self):
        from app.core.session import AgentSession, AgentObservation, AgentSessionStatus

        session = AgentSession(
            task_id="task_1",
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile machine spec",
            input_context={"intent": "Auth flow"},
            max_iterations=2,
        )

        self.assertTrue(session.session_id.startswith("session_"))
        self.assertEqual(session.state.status, AgentSessionStatus.CREATED)
        self.assertEqual(session.state.iteration, 0)
        self.assertEqual(session.max_iterations, 2)

        session.record_observation(AgentObservation(kind="schema", summary="valid json", data={"ok": True}))

        self.assertEqual(len(session.state.observations), 1)
        self.assertEqual(session.state.observations[0].kind, "schema")

    def test_agent_run_result_helpers(self):
        from app.core.errors import DomainError
        from app.core.session import AgentRunResult, AgentSession, AgentSessionStatus

        session = AgentSession(task_id="task_1", step_id="x", agent_role="Compiler", goal="g")
        success = AgentRunResult.succeeded(session=session, content="ok", structured={"a": 1})
        blocked = AgentRunResult.blocked(
            session=session,
            content="bad",
            error=DomainError("x", "blocked"),
            structured={"degraded": True},
        )

        self.assertEqual(success.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(success.structured["a"], 1)
        self.assertEqual(blocked.status, AgentSessionStatus.BLOCKED)
        self.assertTrue(blocked.degraded)
        self.assertEqual(blocked.error.code, "x")


class AgentRuntimeTests(unittest.TestCase):
    def test_runtime_succeeds_with_valid_json_and_records_turn(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class JsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content='{"primary_requirement":"Auth flow"}', structured={})

        session = AgentSession(task_id="task_1", step_id="machine_spec_compiler", agent_role="Compiler", goal="compile")
        result = AgentRuntime(llm=JsonLLM()).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
        )

        self.assertEqual(result.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(result.structured["primary_requirement"], "Auth flow")
        self.assertEqual(session.state.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(session.state.iteration, 1)
        self.assertEqual(len(session.state.turns), 1)

    def test_runtime_blocks_after_invalid_json_retries(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class InvalidJsonLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(content="not json", structured={})

        session = AgentSession(
            task_id="task_1",
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=2,
        )
        result = AgentRuntime(llm=InvalidJsonLLM()).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
        )

        self.assertEqual(result.status, AgentSessionStatus.BLOCKED)
        self.assertTrue(result.degraded)
        self.assertEqual(result.error.code, "agent_runtime.schema_validation_failed")
        self.assertEqual(session.state.status, AgentSessionStatus.BLOCKED)
        self.assertEqual(session.state.iteration, 2)

    def test_runtime_executes_allowed_tool_call_then_converges(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class ToolCallingLLM:
            def __init__(self):
                self.calls = 0

            def invoke(self, role, prompt, context):
                self.calls += 1
                if self.calls == 1:
                    return LLMResult(
                        content='{"tool_calls":[{"tool_name":"knowledge.retrieve","arguments":{"query":"auth"}}]}',
                        structured={},
                    )
                return LLMResult(content='{"primary_requirement":"Auth flow"}', structured={})

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        session = AgentSession(
            task_id=context.task_id,
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=3,
        )

        result = AgentRuntime(llm=ToolCallingLLM(), tool_service=tool_service).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(result.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(result.structured["primary_requirement"], "Auth flow")
        self.assertEqual(session.state.iteration, 2)
        self.assertEqual(session.state.observations[0].kind, "tool")
        self.assertEqual(session.state.observations[0].data["tool_name"], "knowledge.retrieve")
        self.assertEqual(session.state.observations[0].data["status"], "succeeded")

    def test_runtime_blocks_denied_tool_call(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class DeniedToolLLM:
            def invoke(self, role, prompt, context):
                return LLMResult(
                    content='{"tool_calls":[{"tool_name":"artifact.write","arguments":{"name":"x.md","content":"bad"}}]}',
                    structured={},
                )

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        session = AgentSession(
            task_id=context.task_id,
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=2,
        )

        result = AgentRuntime(llm=DeniedToolLLM(), tool_service=tool_service).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(result.status, AgentSessionStatus.BLOCKED)
        self.assertEqual(result.error.code, "agent_runtime.tool_call_denied")
        self.assertEqual(session.state.observations[0].kind, "tool")
        self.assertEqual(session.state.observations[0].data["status"], "denied")

    def test_runtime_uses_provider_native_tool_calling_when_available(self):
        from app.core.session import AgentSession, AgentSessionStatus
        from app.services.agent_runtime import AgentRuntime

        class NativeToolLLM:
            def __init__(self):
                self.calls = 0
                self.received_tools = []
                self.received_tool_messages = []

            def invoke_with_tools(self, role, prompt, context, tools, tool_messages=None):
                self.calls += 1
                self.received_tools.append(tools)
                self.received_tool_messages.append(tool_messages or [])
                if self.calls == 1:
                    return LLMResult(
                        content="",
                        structured={
                            "tool_calls": [
                                {
                                    "id": "call_native_1",
                                    "type": "function",
                                    "function": {
                                        "name": "knowledge.retrieve",
                                        "arguments": '{"query":"auth"}',
                                    },
                                }
                            ]
                        },
                    )
                return LLMResult(content='{"primary_requirement":"Auth flow"}', structured={})

        temp, definition, context, tool_service = make_tool_runtime_context()
        self.addCleanup(temp.cleanup)
        llm = NativeToolLLM()
        session = AgentSession(
            task_id=context.task_id,
            step_id="machine_spec_compiler",
            agent_role="Compiler",
            goal="compile",
            max_iterations=3,
        )

        result = AgentRuntime(llm=llm, tool_service=tool_service).run_json_session(
            session=session,
            prompt="Return JSON",
            context={"intent": "Auth flow"},
            required_keys=["primary_requirement"],
            task_definition=definition,
            task_context=context,
        )

        self.assertEqual(result.status, AgentSessionStatus.SUCCEEDED)
        self.assertEqual(result.structured["primary_requirement"], "Auth flow")
        self.assertEqual(llm.calls, 2)
        self.assertEqual(llm.received_tools[0][0]["function"]["name"], "material__read")
        tool_result_messages = [message for message in llm.received_tool_messages[1] if message.get("role") == "tool"]
        self.assertEqual(tool_result_messages[0]["tool_call_id"], "call_native_1")
        self.assertEqual(session.state.observations[0].data["provider_tool_call_id"], "call_native_1")


if __name__ == "__main__":
    unittest.main()
