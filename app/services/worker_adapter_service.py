"""Worker Adapter Service for handling downstream AI execution."""
from typing import Dict, Any, Protocol

class WorkerTargetType:
    CLI = "cli"
    MCP = "mcp"
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"


class WorkerHandler(Protocol):
    def execute(self, package_path: str) -> Dict[str, Any]:
        ...


class WorkerAdapterService:
    """Service to abstract and dispatch work to downstream AI workers."""
    
    def __init__(self):
        self.adapters: Dict[str, WorkerHandler] = {}

    def register_adapter(self, target_type: str, handler: WorkerHandler) -> None:
        self.adapters[target_type] = handler

    def dispatch(self, package_path: str, target_type: str) -> Dict[str, Any]:
        """Dispatch an agent package to a specific worker type."""
        handler = self.adapters.get(target_type)
        if not handler:
            raise ValueError(f"No adapter registered for {target_type}")
            
        print(f"[*] Dispatching {package_path} to worker type: {target_type}")
        return handler.execute(package_path)
