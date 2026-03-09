"""
graphns/graph.py — The program graph.

Every module, function, type, variable, and import is a node.
Relationships (defines, calls, imports, exports, alias_of, uses, morphism)
are directed labelled edges.

The graph is separate from Python's import machinery — it is a
static semantic layer that tracks what things *mean*, not just how
they are loaded.
"""
from __future__ import annotations
import ast
import inspect
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional


# ── Node kinds ────────────────────────────────────────────────

NODE_MODULE    = "module"
NODE_FUNCTION  = "function"
NODE_CLASS     = "class"
NODE_VARIABLE  = "variable"
NODE_SYMBOL    = "symbol"
NODE_CONTEXT   = "context"    # graph context (semantic region)
NODE_SIG       = "signature"
NODE_ALIAS     = "alias"
NODE_FUNCTOR   = "functor"

# ── Edge relations ────────────────────────────────────────────

REL_DEFINES    = "defines"
REL_CALLS      = "calls"
REL_IMPORTS    = "imports"
REL_EXPORTS    = "exports"
REL_ALIAS_OF   = "alias_of"
REL_USES       = "uses"
REL_MEMBER_OF  = "member_of"   # node is a member of a context
REL_MORPHISM   = "morphism"
REL_IMPLEMENTS = "implements"
REL_RETURNS    = "returns"
REL_INSTANCE   = "instantiates"


@dataclass
class Node:
    name: str
    kind: str
    meta: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"<{self.kind}:{self.name}>"


@dataclass
class Edge:
    src:      str
    relation: str
    dst:      str
    meta:     dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"{self.src!r} --{self.relation}--> {self.dst!r}"


class Graph:
    """
    Directed, labelled, multi-graph of program entities.

    Nodes are keyed by fully-qualified name strings.
    Multiple edges of the same relation between two nodes are allowed.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, Node]            = {}
        self._out:   dict[str, list[Edge]]      = defaultdict(list)
        self._in:    dict[str, list[Edge]]      = defaultdict(list)
        # context membership: context_name -> set of node names
        self._ctx_members: dict[str, set[str]]  = defaultdict(set)
        # membership index: node_name -> set of context names
        self._node_ctxs:   dict[str, set[str]]  = defaultdict(set)

    # ── Node management ───────────────────────────────────────

    def add_node(self, name: str, kind: str, **meta) -> Node:
        if name not in self._nodes:
            self._nodes[name] = Node(name, kind, dict(meta))
        return self._nodes[name]

    def get_node(self, name: str) -> Optional[Node]:
        return self._nodes.get(name)

    def nodes(self, kind: Optional[str] = None) -> list[Node]:
        ns = list(self._nodes.values())
        return [n for n in ns if n.kind == kind] if kind else ns

    # ── Edge management ───────────────────────────────────────

    def add_edge(self, src: str, relation: str, dst: str, **meta) -> Edge:
        e = Edge(src, relation, dst, dict(meta))
        self._out[src].append(e)
        self._in[dst].append(e)
        return e

    def edges_from(self, src: str, relation: Optional[str] = None) -> list[Edge]:
        es = self._out.get(src, [])
        return [e for e in es if e.relation == relation] if relation else list(es)

    def edges_to(self, dst: str, relation: Optional[str] = None) -> list[Edge]:
        es = self._in.get(dst, [])
        return [e for e in es if e.relation == relation] if relation else list(es)

    # ── Context / graph-namespace membership ──────────────────

    def add_to_context(self, node_name: str, ctx_name: str) -> None:
        self._ctx_members[ctx_name].add(node_name)
        self._node_ctxs[node_name].add(ctx_name)
        self.add_edge(node_name, REL_MEMBER_OF, ctx_name)

    def members_of(self, ctx_name: str) -> list[Node]:
        return [self._nodes[n] for n in self._ctx_members.get(ctx_name, set())
                if n in self._nodes]

    def contexts_of(self, node_name: str) -> list[Node]:
        return [self._nodes[c] for c in self._node_ctxs.get(node_name, set())
                if c in self._nodes]

    # ── Convenience builders ──────────────────────────────────

    def record_import(self, importing: str, imported: str) -> None:
        self.add_node(importing, NODE_MODULE)
        self.add_node(imported,  NODE_MODULE)
        self.add_edge(importing, REL_IMPORTS, imported)

    def record_define(self, parent: str, child: str, kind: str) -> None:
        self.add_node(parent, NODE_MODULE)
        self.add_node(child,  kind)
        self.add_edge(parent, REL_DEFINES, child)

    def record_call(self, caller: str, callee: str) -> None:
        self.add_node(callee, NODE_FUNCTION)
        self.add_edge(caller, REL_CALLS, callee)

    def record_export(self, module: str, symbol: str) -> None:
        self.add_node(symbol, NODE_SYMBOL)
        self.add_edge(module, REL_EXPORTS, symbol)

    def record_alias(self, alias: str, original: str) -> None:
        self.add_node(alias, NODE_ALIAS)
        self.add_edge(alias, REL_ALIAS_OF, original)

    # ── AST analysis ─────────────────────────────────────────

    def analyse_source(self, source: str, module_name: str) -> None:
        """Parse a Python source string and add its structure to the graph."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return
        _ASTVisitor(self, module_name).visit(tree)

    def analyse_object(self, obj: Any) -> None:
        """Analyse a live Python object (function, class, module)."""
        try:
            src = inspect.getsource(obj)
        except (TypeError, OSError):
            return
        mod = getattr(obj, "__module__", "<unknown>")
        self.add_node(mod, NODE_MODULE)
        self.analyse_source(src, mod)

    # ── Queries ───────────────────────────────────────────────

    def dependencies(self, name: str) -> list[str]:
        """Direct dependencies (imports + calls) of a node."""
        out = []
        for e in self.edges_from(name):
            if e.relation in (REL_IMPORTS, REL_CALLS, REL_USES):
                out.append(e.dst)
        return out

    def dependents(self, name: str) -> list[str]:
        """Nodes that depend on this one."""
        return [e.src for e in self.edges_to(name)
                if e.relation in (REL_IMPORTS, REL_CALLS, REL_USES)]

    def callers_of(self, name: str) -> list[str]:
        return [e.src for e in self.edges_to(name, REL_CALLS)]

    def callees_of(self, name: str) -> list[str]:
        return [e.dst for e in self.edges_from(name, REL_CALLS)]

    def exports_of(self, name: str) -> list[str]:
        return [e.dst for e in self.edges_from(name, REL_EXPORTS)]

    def find_unused(self) -> list[Node]:
        """Nodes that are defined but never called or used."""
        called = {e.dst for edges in self._in.values() for e in edges
                  if e.relation in (REL_CALLS, REL_USES, REL_IMPORTS)}
        return [n for n in self._nodes.values()
                if n.kind in (NODE_FUNCTION, NODE_VARIABLE) and n.name not in called]

    def find_pure_functions(self) -> list[Node]:
        """Functions that call nothing (heuristic: no outgoing CALLS edges)."""
        return [n for n in self._nodes.values()
                if n.kind == NODE_FUNCTION
                and not self.edges_from(n.name, REL_CALLS)]

    def transitive_deps(self, name: str, visited: Optional[set] = None) -> set[str]:
        if visited is None:
            visited = set()
        if name in visited:
            return visited
        visited.add(name)
        for dep in self.dependencies(name):
            self.transitive_deps(dep, visited)
        return visited

    # ── Context algebra ───────────────────────────────────────

    def ctx_union(self, a: str, b: str, result: str) -> None:
        """result = a ∪ b"""
        self.add_node(result, NODE_CONTEXT)
        for m in self._ctx_members.get(a, set()) | self._ctx_members.get(b, set()):
            self.add_to_context(m, result)

    def ctx_intersect(self, a: str, b: str, result: str) -> None:
        """result = a ∩ b"""
        self.add_node(result, NODE_CONTEXT)
        for m in self._ctx_members.get(a, set()) & self._ctx_members.get(b, set()):
            self.add_to_context(m, result)

    def ctx_diff(self, a: str, b: str, result: str) -> None:
        """result = a − b"""
        self.add_node(result, NODE_CONTEXT)
        for m in self._ctx_members.get(a, set()) - self._ctx_members.get(b, set()):
            self.add_to_context(m, result)

    # ── Display ───────────────────────────────────────────────

    def print_graph(self, *, max_nodes: int = 100, max_edges: int = 200) -> None:
        print(f"\n── Graph ({'nodes': <6} {len(self._nodes)}, {'edges': <6} {sum(len(v) for v in self._out.values())}) ──")
        print("\nNodes:")
        for i, n in enumerate(self._nodes.values()):
            if i >= max_nodes: print(f"  ... ({len(self._nodes)-max_nodes} more)"); break
            print(f"  {n}")
        print("\nEdges:")
        count = 0
        for edges in self._out.values():
            for e in edges:
                if count >= max_edges:
                    print(f"  ... (more edges not shown)")
                    return
                print(f"  {e}")
                count += 1

    def summary(self) -> str:
        n = len(self._nodes)
        e = sum(len(v) for v in self._out.values())
        kinds: dict[str,int] = defaultdict(int)
        for node in self._nodes.values():
            kinds[node.kind] += 1
        ks = ", ".join(f"{k}={v}" for k,v in sorted(kinds.items()))
        return f"Graph({n} nodes [{ks}], {e} edges)"


# ── AST visitor ───────────────────────────────────────────────

class _ASTVisitor(ast.NodeVisitor):

    def __init__(self, graph: Graph, module: str) -> None:
        self._g   = graph
        self._mod = module
        self._fn_stack: list[str] = []
        self._g.add_node(module, NODE_MODULE)

    @property
    def _current(self) -> str:
        return self._fn_stack[-1] if self._fn_stack else self._mod

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name   = alias.name
            asname = alias.asname or name
            self._g.record_import(self._mod, name)
            if alias.asname:
                self._g.record_alias(asname, name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        self._g.record_import(self._mod, mod)
        for alias in node.names:
            sym    = f"{mod}.{alias.name}"
            asname = alias.asname or alias.name
            self._g.add_node(sym, NODE_SYMBOL)
            self._g.add_edge(self._mod, REL_USES, sym)
            if alias.asname:
                self._g.record_alias(asname, sym)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qname = f"{self._current}.{node.name}"
        self._g.record_define(self._current, qname, NODE_FUNCTION)
        self._fn_stack.append(qname)
        self.generic_visit(node)
        self._fn_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qname = f"{self._current}.{node.name}"
        self._g.record_define(self._current, qname, NODE_CLASS)
        self._fn_stack.append(qname)
        self.generic_visit(node)
        self._fn_stack.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                vname = f"{self._current}.{target.id}"
                self._g.record_define(self._current, vname, NODE_VARIABLE)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self._g.record_call(self._current, node.func.id)
        elif isinstance(node.func, ast.Attribute):
            callee = f"{_name_of(node.func.value)}.{node.func.attr}"
            self._g.record_call(self._current, callee)
        self.generic_visit(node)


def _name_of(node: ast.expr) -> str:
    if isinstance(node, ast.Name):       return node.id
    if isinstance(node, ast.Attribute):  return f"{_name_of(node.value)}.{node.attr}"
    return "<expr>"
