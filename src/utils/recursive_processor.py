"""
Minimal recursive processor shim to satisfy legacy imports.
"""

from typing import Any, Dict


def process_recursive(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return {"executed": True}


def deep_copy(obj: Any) -> Any:
    try:
        import copy
        return copy.deepcopy(obj)
    except Exception as e:
        from src.utils.error_handler import handle_exception
        handle_exception(e, "recursive_processor_deep_copy", {
            "obj_type": type(obj).__name__
        }, is_critical=False, continue_execution=True)
        return obj


