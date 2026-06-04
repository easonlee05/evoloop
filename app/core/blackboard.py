"""Blackboard for shared working memory in 3.0 Playbook DAG."""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class BlackboardContext:
    """A slice of the product context shared on the blackboard."""
    key: str
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    owner_node: str = "system"


@dataclass
class BlackboardSlot:
    """A slot metadata definition on the blackboard with permissions and types."""
    key: str
    data_type: Any = Any
    allowed_writers: List[str] = field(default_factory=list)
    allowed_readers: List[str] = field(default_factory=list)

    def validate_value(self, value: Any) -> None:
        """Validate if value matches data_type."""
        if self.data_type is Any or self.data_type is None:
            return
        
        from typing import get_origin, get_args, Union
        origin = get_origin(self.data_type)
        
        if origin is Union:
            is_valid = False
            for arg in get_args(self.data_type):
                arg_origin = get_origin(arg)
                arg_check = arg_origin if arg_origin is not None else arg
                if arg_check is Any or arg_check is None:
                    is_valid = True
                    break
                try:
                    if isinstance(value, arg_check):
                        is_valid = True
                        break
                except TypeError:
                    pass
        else:
            check_type = origin if origin is not None else self.data_type
            if check_type is Any:
                return
            
            try:
                is_valid = isinstance(value, check_type)
            except TypeError:
                is_valid = True
        
        if not is_valid:
            raise TypeError(f"Value for slot '{self.key}' must be of type {self.data_type}, got {type(value)}")


class Blackboard:
    """Shared state mechanism across DAG nodes."""
    def __init__(self, strict: bool = False):
        self.strict = strict
        self._store: Dict[str, BlackboardContext] = {}
        self._slots: Dict[str, BlackboardSlot] = {}
        self._audit_callback = None

    def set_audit_callback(self, callback) -> None:
        """Set the audit callback for blackboard actions."""
        self._audit_callback = callback

    def _audit(self, caller_id: str, action: str, key: str, success: bool, error_message: str = None) -> None:
        """Trigger audit callback if registered."""
        if self._audit_callback:
            try:
                self._audit_callback(caller_id, action, key, success, error_message)
            except Exception as e:
                logger.warning(f"Failed to execute audit callback: {e}")

    def load_slots_from_dict(self, data: List[Dict[str, Any]]) -> None:
        """Dynamically load slot definitions from a list of dicts."""
        type_map = {
            "int": int,
            "str": str,
            "dict": dict,
            "list": list,
            "bool": bool,
            "float": float,
            "any": Any,
            "Any": Any
        }
        for item in data:
            raw_type = item.get("data_type", "any")
            parsed_type = type_map.get(raw_type, Any) if isinstance(raw_type, str) else raw_type
            slot = BlackboardSlot(
                key=item["key"],
                data_type=parsed_type,
                allowed_writers=list(item.get("allowed_writers", [])),
                allowed_readers=list(item.get("allowed_readers", []))
            )
            self.register_slot(slot)

    def register_slot(self, slot: BlackboardSlot) -> None:
        """Register a slot definition on the blackboard."""
        self._slots[slot.key] = slot

    def write(self, key: str, value: Any, caller_id: str = None, owner_node: str = None, **metadata) -> None:
        """Write a slice to the blackboard with caller_id authorization and type safety checking."""
        actual_caller = caller_id or owner_node or "system"
        
        try:
            if self.strict and key not in self._slots:
                raise KeyError(f"Key '{key}' is not pre-registered in strict mode")
                
            if key in self._slots:
                slot = self._slots[key]
                if slot.allowed_writers and actual_caller not in slot.allowed_writers:
                    raise PermissionError(f"Caller '{actual_caller}' is not authorized to write to slot '{key}'")
                slot.validate_value(value)
                
            self._store[key] = BlackboardContext(key=key, value=value, metadata=metadata, owner_node=actual_caller)
            self._audit(actual_caller, "write", key, True)
        except Exception as err:
            self._audit(actual_caller, "write", key, False, str(err))
            raise

    def read(self, key: str, caller_id: str = None) -> Any:
        """Read a slice from the blackboard with caller_id authorization checking."""
        actual_caller = caller_id or "system"
        try:
            if self.strict and key not in self._slots:
                raise KeyError(f"Key '{key}' is not pre-registered in strict mode")

            if key in self._slots:
                slot = self._slots[key]
                if slot.allowed_readers and actual_caller not in slot.allowed_readers:
                    raise PermissionError(f"Caller '{actual_caller}' is not authorized to read from slot '{key}'")
                    
            ctx = self._store.get(key)
            val = ctx.value if ctx else None
            self._audit(actual_caller, "read", key, True)
            return val
        except Exception as err:
            self._audit(actual_caller, "read", key, False, str(err))
            raise

    def list_keys(self) -> List[str]:
        return list(self._store.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.value for k, v in self._store.items()}
