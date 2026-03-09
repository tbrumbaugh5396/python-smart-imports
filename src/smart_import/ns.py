"""
graphns/ns.py — The global graph namespace and context system.

This is the top-level controller that ties everything together:
  - a single program Graph
  - a stack of active contexts (for name resolution)
  - open_module() — inject exports into a caller's namespace
  - GraphContext   — a named semantic region containing modules/functions
  - context algebra: union, intersection, difference
  - morphisms between contexts

The global `namespace` object is the main entry point for users.
"""
from __future__ import annotations
import sys
import importlib
import inspect
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional, Type

from graphns.graph  import (
    Graph, Node,
    NODE_MODULE, NODE_CONTEXT, NODE_SYMBOL, NODE_FUNCTION,
    REL_EXPORTS, REL_IMPORTS, REL_MEMBER_OF, REL_MORPHISM,
)
from graphns.sig    import Sig
from graphns.module import Module


# ── GraphContext ──────────────────────────────────────────────

class GraphContext:
    """
    A named semantic region of the program graph.

    This is the *graph context* (not the typing context):
    it groups definitions by conceptual domain rather than
    by file or directory.

    Usage:

        algo = namespace.context("Algorithm")
        algo.add(sort_fn, "sort")
        algo.add(search_fn, "search")

        sorting = namespace.intersect("Algorithm", "Arrays", name="Sorting")
    """

    def __init__(self, name: str, graph: Graph) -> None:
        self.name  = name
        self._g    = graph
        graph.add_node(name, NODE_CONTEXT)

    def add(self, obj: Any, export_name: Optional[str] = None) -> None:
        """Add a Python object (function, Module, etc.) as a member."""
        name = export_name or getattr(obj, "__name__", repr(obj))
        kind = NODE_FUNCTION if callable(obj) else NODE_SYMBOL
        self._g.add_node(name, kind, value=obj)
        self._g.add_to_context(name, self.name)

    def add_module(self, mod: Module) -> None:
        """Add all exports of a Module as members of this context."""
        self._g.add_node(mod._name, NODE_MODULE)
        self._g.add_to_context(mod._name, self.name)
        for sym in mod.keys():
            full = f"{mod._name}.{sym}"
            self._g.add_to_context(full, self.name)

    def members(self) -> list[Node]:
        return self._g.members_of(self.name)

    def resolve(self, name: str) -> Optional[Any]:
        """Look up a name within this context."""
        for node in self.members():
            if node.name == name or node.name.endswith(f".{name}"):
                return node.meta.get("value")
        return None

    def __repr__(self) -> str:
        mems = [n.name for n in self.members()]
        return f"<GraphContext {self.name!r} [{', '.join(mems)}]>"


# ── Morphism ──────────────────────────────────────────────────

class Morphism:
    """
    A structure-preserving map between two GraphContexts.

    OCaml equivalent:
        module SqlToFP = struct
          let select = map
          let where_ = filter
        end

    graphns:
        m = namespace.morphism("SqlToFP", src="SQL", tgt="Functional",
                               mapping={"select": "map", "where_": "filter"})
        fp_filter = m.apply("where_")
    """

    def __init__(
        self,
        name:    str,
        src_ctx: GraphContext,
        tgt_ctx: GraphContext,
        mapping: dict[str, str],
        graph:   Graph,
    ) -> None:
        self.name    = name
        self._src    = src_ctx
        self._tgt    = tgt_ctx
        self._map    = mapping
        self._g      = graph
        graph.add_node(name, "morphism", src=src_ctx.name, tgt=tgt_ctx.name)
        for s, t in mapping.items():
            graph.add_edge(f"{src_ctx.name}.{s}", REL_MORPHISM, f"{tgt_ctx.name}.{t}",
                           morphism=name)

    def apply(self, src_name: str) -> Optional[Any]:
        """Apply the morphism: look up src_name in src, return tgt value."""
        tgt_name = self._map.get(src_name)
        if tgt_name is None:
            return None
        return self._tgt.resolve(tgt_name)

    def __repr__(self) -> str:
        return f"<Morphism {self.name!r}: {self._src.name} → {self._tgt.name}>"


# ── Namespace ─────────────────────────────────────────────────

class Namespace:
    """
    The global graph namespace.

    Combines:
      - A program Graph (all nodes and edges)
      - A registry of named Modules, GraphContexts, and Morphisms
      - An active-context stack for name resolution
      - open_module() for OCaml-style `open`
      - ocaml_import() for ML-style qualified imports
    """

    def __init__(self) -> None:
        self.graph     = Graph()
        self._modules:  dict[str, Module]       = {}
        self._contexts: dict[str, GraphContext] = {}
        self._morphisms:dict[str, Morphism]     = {}
        self._ctx_stack: list[str]              = []

    # ── Module management ─────────────────────────────────────

    def register(self, mod: Module) -> Module:
        """Register a Module in this namespace."""
        self._modules[mod._name] = mod
        return mod

    def get_module(self, name: str) -> Optional[Module]:
        return self._modules.get(name)

    # ── OCaml-style import ────────────────────────────────────

    def ocaml_import(
        self,
        module_path:  str,
        alias:        Optional[str]      = None,
        sig:          Optional[Type[Sig]] = None,
        open_:        bool               = False,
        caller_ns:    Optional[dict]     = None,
    ) -> Module:
        """
        Import a module with OCaml-style semantics.

        Parameters
        ----------
        module_path : str
            Dotted Python module path, e.g. "math" or "os.path".
        alias : str, optional
            Local name for the module (like `module M = Math` in OCaml).
        sig : Sig subclass, optional
            Signature to enforce. Only declared members are exposed.
        open_ : bool
            If True, inject all exports into caller_ns (like `open M` in OCaml).
        caller_ns : dict, optional
            The namespace to inject into when open_=True. Pass globals().

        Returns
        -------
        Module
            The sealed module object.

        Examples
        --------
            Math = namespace.ocaml_import("math", alias="Math", sig=MathSig)
            Math.sqrt(16)

            namespace.ocaml_import("math", open_=True, caller_ns=globals())
            sqrt(16)   # now in scope
        """
        name = alias or module_path
        mod  = Module(module_path, sig=sig, alias=name, graph=self.graph)
        self._modules[name] = mod

        if open_ and caller_ns is not None:
            _inject(mod.exports(), caller_ns)

        return mod

    def open(self, name_or_mod: "str | Module", caller_ns: dict) -> None:
        """
        OCaml `open M` — inject all exports of a module into caller_ns.

            namespace.open("Math", globals())
        """
        if isinstance(name_or_mod, str):
            mod = self._modules.get(name_or_mod)
            if mod is None:
                # Try importing it on the fly
                mod = self.ocaml_import(name_or_mod)
        else:
            mod = name_or_mod
        _inject(mod.exports(), caller_ns)

    # ── Context management ────────────────────────────────────

    def context(self, name: str) -> GraphContext:
        """Get or create a named GraphContext."""
        if name not in self._contexts:
            self._contexts[name] = GraphContext(name, self.graph)
        return self._contexts[name]

    def push_context(self, name: str) -> None:
        """Push a context onto the active resolution stack."""
        self._ctx_stack.append(name)

    def pop_context(self) -> None:
        if self._ctx_stack:
            self._ctx_stack.pop()

    @contextmanager
    def active(self, *context_names: str) -> Iterator[None]:
        """
        Context manager: activate named contexts for the duration.

            with namespace.active("Algorithm", "Arrays"):
                # sort resolves from these contexts
        """
        for name in context_names:
            self.push_context(name)
        try:
            yield
        finally:
            for _ in context_names:
                self.pop_context()

    def resolve(self, name: str) -> Optional[Any]:
        """
        Resolve a name through the active context stack (innermost first).
        Raises NameError on ambiguity.
        """
        candidates = []
        for ctx_name in reversed(self._ctx_stack):
            ctx = self._contexts.get(ctx_name)
            if ctx:
                val = ctx.resolve(name)
                if val is not None:
                    candidates.append((ctx_name, val))
        if len(candidates) == 1:
            return candidates[0][1]
        if len(candidates) > 1:
            origins = [c[0] for c in candidates]
            raise NameError(
                f"Ambiguous name {name!r}: found in contexts {origins}. "
                f"Use qualified access, e.g. namespace.context('Algorithm').resolve('sort')"
            )
        return None

    # ── Context algebra ───────────────────────────────────────

    def union(self, a: str, b: str, name: str) -> GraphContext:
        """result = a ∪ b"""
        self.graph.ctx_union(a, b, name)
        ctx = GraphContext(name, self.graph)
        self._contexts[name] = ctx
        return ctx

    def intersect(self, a: str, b: str, name: str) -> GraphContext:
        """result = a ∩ b"""
        self.graph.ctx_intersect(a, b, name)
        ctx = GraphContext(name, self.graph)
        self._contexts[name] = ctx
        return ctx

    def diff(self, a: str, b: str, name: str) -> GraphContext:
        """result = a − b"""
        self.graph.ctx_diff(a, b, name)
        ctx = GraphContext(name, self.graph)
        self._contexts[name] = ctx
        return ctx

    # ── Morphisms ─────────────────────────────────────────────

    def morphism(
        self,
        name:    str,
        src:     str,
        tgt:     str,
        mapping: dict[str, str],
    ) -> Morphism:
        """
        Define a morphism between two contexts.

            m = namespace.morphism("SqlToFP",
                    src="SQL", tgt="Functional",
                    mapping={"select": "map", "where_": "filter"})
        """
        src_ctx = self.context(src)
        tgt_ctx = self.context(tgt)
        m = Morphism(name, src_ctx, tgt_ctx, mapping, self.graph)
        self._morphisms[name] = m
        return m

    # ── Queries ───────────────────────────────────────────────

    def what_context(self, name: str) -> list[str]:
        """Which contexts does this node belong to?"""
        return [n.name for n in self.graph.contexts_of(name)]

    def who_calls(self, name: str) -> list[str]:
        return self.graph.callers_of(name)

    def dependencies_of(self, name: str) -> list[str]:
        return self.graph.dependencies(name)

    def unused(self) -> list[Node]:
        return self.graph.find_unused()

    def summary(self) -> str:
        mods  = len(self._modules)
        ctxs  = len(self._contexts)
        morps = len(self._morphisms)
        return (f"Namespace: {mods} modules, {ctxs} contexts, "
                f"{morps} morphisms | {self.graph.summary()}")

    def print_graph(self, **kw) -> None:
        self.graph.print_graph(**kw)


# ── Module-level helpers ──────────────────────────────────────

def _inject(exports: dict[str, Any], ns: dict) -> None:
    """Inject exports into a namespace dict, skipping private names."""
    for k, v in exports.items():
        if not k.startswith("_"):
            ns[k] = v


# ── open_module — standalone convenience function ─────────────

def open_module(
    source: "str | Module",
    caller_ns: Optional[dict] = None,
    sig: Optional[Type[Sig]] = None,
) -> Module:
    """
    Standalone `open_module()` — load and inject a module's exports.

    Parameters
    ----------
    source : str or Module
        Module path string or an existing Module object.
    caller_ns : dict, optional
        Namespace to inject into. If None, uses the caller's globals().
    sig : Sig subclass, optional
        Signature to enforce.

    Examples
    --------
        open_module("math", globals())
        print(sqrt(16))   # 4.0

        open_module("math", globals(), sig=MathSig)
    """
    if caller_ns is None:
        frame = inspect.currentframe()
        if frame and frame.f_back:
            caller_ns = frame.f_back.f_globals

    if isinstance(source, str):
        mod = Module(source, sig=sig, graph=namespace.graph)
    else:
        mod = source

    if caller_ns is not None:
        _inject(mod.exports(), caller_ns)

    namespace.register(mod)
    return mod


# ── Global namespace singleton ────────────────────────────────

namespace = Namespace()
