"""Utility functions for Evoloop 3.0 CLI Adapter."""
from __future__ import annotations

import os
import sys
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None


def compact_error_text(text: str, max_lines: int = 25) -> str:
    """Compact very long tracebacks or command outputs to adhere to L1/L2 principles.
    
    If text length in lines is larger than max_lines, keep first half and last half
    and fold the middle lines with a descriptive marker.
    """
    if not text:
        return ""
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
        
    half = (max_lines - 1) // 2
    header = lines[:half]
    footer = lines[-half:]
    skipped_count = len(lines) - len(header) - len(footer)
    
    compacted = (
        header + 
        [f"... [Folded {skipped_count} lines of output due to L1/L2 Compaction principles] ..."] + 
        footer
    )
    return "\n".join(compacted)


def read_yaml_safe(path: str) -> Optional[dict[str, Any]]:
    """Safely read and parse a YAML file.
    
    Fallback to JSON or print error if YAML parser is missing or file is corrupt.
    """
    if not os.path.exists(path):
        return None
    try:
        content = Path(path).read_text(encoding="utf-8")
        if yaml is not None:
            return yaml.safe_load(content)
        else:
            # Fallback for simple key-value YAML to JSON if pyyaml is missing (unlikely)
            import json
            try:
                return json.loads(content)
            except Exception:
                raise ImportError("pyyaml is required to read complex YAML files.")
    except Exception as e:
        print(f"Error reading YAML file at {path}: {compact_error_text(str(e))}", file=sys.stderr)
        return None


def write_yaml_safe(path: str, data: dict[str, Any]) -> bool:
    """Safely write data structure into a YAML file."""
    try:
        from pathlib import Path
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        if yaml is not None:
            content = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
        else:
            import json
            content = json.dumps(data, ensure_ascii=False, indent=2)
            
        dest.write_text(content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"Error writing YAML file to {path}: {compact_error_text(str(e))}", file=sys.stderr)
        return False

# Quick Path wrapper inside utils for safety
from pathlib import Path
