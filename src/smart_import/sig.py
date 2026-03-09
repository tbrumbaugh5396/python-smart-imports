"""
graphns/sig.py — Module signatures (OCaml-style interfaces / .mli files).

A Sig defines the *public contract* of a module:
  - which names must be exported
  - optional type annotations (checked at runtime via isinstance)
  - optional doc strings per member

Example:

    class MathSig(Sig):
        add : callable
        mul : callable

Any module loaded against MathSig must export `add` and `mul`.
Internal helpers (_helper, _cache, etc.) are automatically hidden.
"""
from __future__ import annotations
import typing
from typing import Any, get_type_hints


class SigViolation(TypeError):
    """Raised when a module does not satisfy its signature."""


class _SigMeta(type):
    """Metaclass that collects annotated members as the public interface."""

    def __new__(mcs, name, bases, ns):
        cls = super().__new__(mcs, name, bases, ns)
        # Collect all annotations from this class and its Sig bases
        members: dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            if base is object: continue
            ann = base.__dict__.get("__annotations__", {})
            members.update(ann)
        # Strip private and dunder names — they are never sig members
        cls._sig_members: dict[str, Any] = {
            k: v for k, v in members.items()
            if not k.startswith("_")
        }
        return cls

    def __repr__(cls) -> str:
        mems = ", ".join(cls._sig_members.keys())
        return f"<Sig {cls.__name__} [{mems}]>"


class Sig(metaclass=_SigMeta):
    """
    Base class for module signatures.

    Subclass it and add annotations to declare the public API:

        class MathSig(Sig):
            add : callable
            mul : callable
            PI  : float

    Type annotations are used for runtime type checking when a module
    is loaded against this signature.
    """
    _sig_members: dict[str, Any] = {}

    @classmethod
    def check(cls, exports: dict[str, Any]) -> dict[str, Any]:
        """
        Verify that `exports` satisfies this signature.
        Returns the filtered exports dict (only the sig members).
        Raises SigViolation on missing or type-mismatched members.
        """
        result: dict[str, Any] = {}
        for name, expected_type in cls._sig_members.items():
            if name not in exports:
                raise SigViolation(
                    f"Module missing required member {name!r} "
                    f"(declared in signature {cls.__name__!r})"
                )
            value = exports[name]
            if expected_type is not None and expected_type is not Any:
                if not _type_check(value, expected_type):
                    raise SigViolation(
                        f"Member {name!r} has type {type(value).__name__!r}, "
                        f"expected {_type_name(expected_type)!r} "
                        f"(signature {cls.__name__!r})"
                    )
            result[name] = value
        return result

    @classmethod
    def members(cls) -> list[str]:
        return list(cls._sig_members.keys())

    @classmethod
    def is_compatible(cls, exports: dict[str, Any]) -> bool:
        """True if exports satisfies this signature without raising."""
        try:
            cls.check(exports)
            return True
        except SigViolation:
            return False


# ── Type checking helpers ─────────────────────────────────────

def _type_check(value: Any, expected: Any) -> bool:
    """Best-effort runtime type check."""
    # callable is a special case — check with callable()
    if expected is callable:
        return callable(value)
    # typing generics (List[int], etc.) — just check origin
    origin = getattr(expected, "__origin__", None)
    if origin is not None:
        return isinstance(value, origin)
    # Plain type
    if isinstance(expected, type):
        return isinstance(value, expected)
    return True   # unknown annotation → pass


def _type_name(t: Any) -> str:
    if t is callable: return "callable"
    if hasattr(t, "__name__"): return t.__name__
    return str(t)
