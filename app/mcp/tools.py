"""Tools registration for the MCP server."""
import os
import json
from typing import List, Optional

def get_service():
    from app.cli.commands import build_cli_task_service
    output_dir = os.environ.get("EVOLOOP_WORKSPACE", os.getcwd())
    return build_cli_task_service(output_dir)

def register_tools(mcp):
    
    @mcp.tool()
    def get_project_context(task_id: str) -> str:
        """Get the cross-round ProductContext for a given task, exposing objective, requirements and decisions."""
        svc = get_service()
        try:
            ctx = svc.get_product_context(task_id)
            return json.dumps({
                "objective": ctx.objective,
                "requirements": [r.to_dict() for r in ctx.requirements],
                "decisions": [d.to_dict() for d in ctx.user_decisions]
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def compile_spec(intent: str, material_ids: Optional[List[str]] = None) -> str:
        """Compile a business intent into machine_spec.yaml and human_brief.md."""
        svc = get_service()
        payload = {
            "username": "mcp_worker",
            "business_intent": intent,
            "material_ids": material_ids or []
        }
        try:
            task = svc.create_task("spec_to_agent", payload)
            svc.run_task(task.task_id)
            return f"Task created and started. Task ID: {task.task_id}. Please check status or context later."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def request_decision(task_id: str, decision_text: str) -> str:
        """Apply a decision to a pending DecisionGate in the PM workflow."""
        svc = get_service()
        try:
            task = svc.apply_decision(task_id, decision=decision_text)
            svc.run_task(task.task_id)
            return f"Decision applied. Task status is now {task.status.value}."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def get_agent_package(spec_path: str, output_path: str) -> str:
        """Generate an agent_package.md based on a machine_spec.yaml to handoff work to downstream AI workers."""
        from app.cli.commands import package_cmd
        try:
            package_cmd(spec_path, output_path, fake=False)
            return f"Package successfully written to {output_path}."
        except SystemExit:
            return "Package generation failed. Check server logs."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def get_acceptance(spec_path: str, output_path: str) -> str:
        """Generate an acceptance.md protocol based on machine_spec.yaml for QA and testing constraints."""
        from app.cli.commands import acceptance_cmd
        try:
            acceptance_cmd(spec_path, output_path, fake=False)
            return f"Acceptance protocol successfully written to {output_path}."
        except SystemExit:
            return "Acceptance generation failed."
        except Exception as e:
            return f"Error: {e}"

    @mcp.tool()
    def create_requirement(task_id: str, statement: str) -> str:
        """Add a specific requirement to the current product context directly."""
        svc = get_service()
        try:
            ctx = svc.get_product_context(task_id)
            import uuid
            new_id = f"req_{uuid.uuid4().hex[:6]}"
            from app.core.playbook import Requirement
            ctx.requirements.append(Requirement(requirement_id=new_id, statement=statement))
            return f"Requirement {new_id} added successfully."
        except Exception as e:
            return f"Error: {e}"
