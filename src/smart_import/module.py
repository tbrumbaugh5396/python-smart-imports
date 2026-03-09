"""
graphns/module.py — Signature-enforced module objects.

A Module wraps a Python module (or any dict of exports) and:
  - enforces a Sig (if provided)
  - hides all private members (names starting with _)
  - exposes only declared-public members
  - supports qualified attribute access  (Math.add)
  - registers itself in the program graph

This is the Python equivalent of:

    module Math : MATH_SIG = struct ... end
"""
from __future__ import annotations
import importlib
import importlib.util
import inspect
import sys
import types
from typing import Any, Optional, Type

from graphns.sig   import Sig, SigViolation
from graphns.graph import (
    Graph, NODE_MODULE, NODE_SYMBOL,
    REL_EXPORTS, REL_IMPORTS, REL_ALIAS_OF,
)


class ModuleError(ImportError):
    """Raised when a module cannot be loaded or sealed."""


class Module:
    """
    An OCaml-style module: a named, signature-sealed namespace.

    Construction:

        Math = Module("math", sig=MathSig)
        Math = Module.from_dict("Math", {"add": lambda a,b: a+b}, sig=MathSig)

    Access:

        Math.add(1, 2)          # qualified access
        Math["add"]             # dict-style access
        vars(Math)              # all exported symbols as dict
    """

    def __init__(
        self,
        module_path:  str,
        sig:          Optional[Type[Sig]] = None,
        alias:        Optional[str] = None,
        graph:        Optional[Graph] = None,
        package_root: Optional[str] = None,
    ) -> None:
        self._name  = alias or module_path
        self._sig   = sig
        self._graph = graph

        # Load the underlying Python module
        raw = _load_module(module_path, package_root)
        self._source_name = module_path

        # Build the raw exports dict (exclude private names)
        raw_exports = {
            k: getattr(raw, k)
            for k in dir(raw)
            if not k.startswith("_")
        }

        # Apply signature filter / check
        if sig is not None:
            self._exports = sig.check(raw_exports)
        else:
            self._exports = raw_exports

        # Register in graph
        if graph is not None:
            self._register_graph(graph, module_path, alias)

    @classmethod
    def from_dict(
        cls,
        name:    str,
        exports: dict[str, Any],
        sig:     Optional[Type[Sig]] = None,
        graph:   Optional[Graph] = None,
    ) -> "Module":
        """Create a module directly from a dict of exports (no file needed)."""
        obj = object.__new__(cls)
        obj._name        = name
        obj._sig         = sig
        obj._graph       = graph
        obj._source_name = name

        # Exclude private names
        raw = {k: v for k, v in exports.items() if not k.startswith("_")}

        if sig is not None:
            obj._exports = sig.check(raw)
        else:
            obj._exports = raw

        if graph is not None:
            obj._register_graph(graph, name, None)

        return obj

    # ── Attribute access ─────────────────────────────────────

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._exports[name]
        except KeyError:
            raise AttributeError(
                f"Module {self._name!r} has no exported member {name!r}. "
                f"Exported: {list(self._exports.keys())}"
            )

    def __getitem__(self, name: str) -> Any:
        try:
            return self._exports[name]
        except KeyError:
            raise KeyError(
                f"Module {self._name!r} has no exported member {name!r}"
            )

    def __contains__(self, name: str) -> bool:
        return name in self._exports

    def __iter__(self):
        return iter(self._exports)

    def __repr__(self) -> str:
        sig_s = f" : {self._sig.__name__}" if self._sig else ""
        mems  = ", ".join(self._exports.keys())
        return f"<Module {self._name!r}{sig_s} [{mems}]>"

    # ── Dict-like interface ───────────────────────────────────

    def exports(self) -> dict[str, Any]:
        """Return a copy of the exports dict."""
        return dict(self._exports)

    def keys(self) -> list[str]:
        return list(self._exports.keys())

    # ── Graph registration ────────────────────────────────────

    def _register_graph(self, g: Graph, module_path: str, alias: Optional[str]) -> None:
        g.add_node(self._name, NODE_MODULE, sig=self._sig.__name__ if self._sig else None)
        if module_path != self._name:
            g.record_import(self._name, module_path)
        if alias and alias != module_path:
            g.record_alias(alias, module_path)
        for sym in self._exports:
            g.add_node(f"{self._name}.{sym}", NODE_SYMBOL)
            g.add_edge(self._name, REL_EXPORTS, f"{self._name}.{sym}")


# ── Loader helper ─────────────────────────────────────────────

def _load_module(module_path: str, package_root: Optional[str] = None) -> types.ModuleType:
    """Load a module by dotted path, optionally adding package_root to sys.path."""
    if package_root is not None and package_root not in sys.path:
        sys.path.insert(0, package_root)
    try:
        return importlib.import_module(module_path)
    except ImportError as e:
        raise ModuleError(f"Cannot import {module_path!r}: {e}") from e
