"""
graph_based_namespaces/context_expression.py — Lazy context expression tree.

A ContextExpression is a *description* of a set of graph nodes.
Nothing is computed until .members() or .resolve() is called.
At that point the expression tree is evaluated bottom-up against
the *current* state of the graph — so new nodes added after the
expression was built are automatically included.

Expression nodes
────────────────
  ContextReference(name)          — a named context already in the graph
  ContextAll(kind)          — every node of a given kind (the universe)
  ContextUnion(a, b)        — a ∪ b
  ContextIntersection(a, b)    — a ∩ b
  ContextDifference(a, b)         — a \\ b  (in a but not in b)
  ContextComplement(a)      — NOT a  (requires a universe to subtract from)
  ContextFilter(a, pred)    — filter members of a by a predicate

All ContextExpression subclasses support Python operators:
  expr_a | expr_b       → ContextUnion
  expr_a & expr_b       → ContextIntersection
  expr_a - expr_b       → ContextDifference
  ~expr_a               → ContextComplement (universe = ContextAll)

Usage
─────
  from graph_based_namespaces.context_expression import ContextReference, ContextAll

  a     = ContextReference("A", graph)
  b     = ContextReference("B", graph)
  not_a = ~a                      # lazy — nothing computed yet
  expr  = (a & b) | (b - a)       # lazy composition

  expr.members()                  # evaluated NOW against current graph
  expr.resolve("double")          # find a node by name in the result
"""
from __future__ import annotations
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from graph_based_namespaces.graph import Graph, Node


# ── Base ──────────────────────────────────────────────────────

class ContextExpression:
    """
    Abstract base for lazy context expressions.
    Subclasses implement _eval(graph) → set[str]  (set of node names).
    """

    # ── Core interface ────────────────────────────────────────

    def _eval(self, graph: "Graph") -> set[str]:
        raise NotImplementedError

    def members(self, kind: Optional[str] = None) -> list["Node"]:
        """
        Evaluate the expression and return matching Node objects.

        Parameters
        ----------
        kind : str, optional
            If given, only return nodes of this kind
            (e.g. "function", "module", "concept").
        """
        names = self._eval(self._graph)
        nodes = [self._graph.get_node(n) for n in names
                 if self._graph.get_node(n) is not None]
        if kind:
            nodes = [n for n in nodes if n.kind == kind]
        return sorted(nodes, key=lambda n: n.name)

    def resolve(self, name: str) -> Optional[Any]:
        """Find a node by name in this expression's result and return its value."""
        names = self._eval(self._graph)
        if name in names:
            node = self._graph.get_node(name)
            if node:
                return node.meta.get("value")
        # Also try suffix match (e.g. "double" matches "A.double")
        for n in names:
            if n == name or n.endswith(f".{name}"):
                node = self._graph.get_node(n)
                if node:
                    return node.meta.get("value")
        return None

    def names(self) -> set[str]:
        """Return the raw set of node names (no Node objects)."""
        return self._eval(self._graph)

    # ── Operator overloads — lazy composition ─────────────────

    def __or__(self, other: "ContextExpression") -> "ContextUnion":
        return ContextUnion(self, _coerce(other, self._graph))

    def __and__(self, other: "ContextExpression") -> "ContextIntersection":
        return ContextIntersection(self, _coerce(other, self._graph))

    def __sub__(self, other: "ContextExpression") -> "ContextDifference":
        return ContextDifference(self, _coerce(other, self._graph))

    def __invert__(self) -> "ContextComplement":
        return ContextComplement(self, ContextAll(self._graph))

    def filter(self, pred: Callable[["Node"], bool]) -> "ContextFilter":
        """Return a filtered sub-expression."""
        return ContextFilter(self, pred)

    # ── Display ───────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"

    def explain(self, indent: int = 0) -> str:
        """Pretty-print the expression tree."""
        return "  " * indent + repr(self)


# ── Leaf nodes ────────────────────────────────────────────────

class ContextReference(ContextExpression):
    """A named context already registered in the graph."""

    def __init__(self, name: str, graph: "Graph") -> None:
        self.name   = name
        self._graph = graph

    def _eval(self, graph: "Graph") -> set[str]:
        return set(graph._context_members.get(self.name, set()))

    def __repr__(self) -> str:
        return f"ContextReference({self.name!r})"

    def explain(self, indent: int = 0) -> str:
        names = sorted(self._eval(self._graph))
        return "  " * indent + f"ContextReference({self.name!r})  → {names}"


class ContextAll(ContextExpression):
    """
    The universe — every node in the graph, optionally filtered by kind.

    ~ContextReference("A") expands to ContextComplement(ContextReference("A"), ContextAll())
    so NOT A means "everything in the graph that isn't in A".
    """

    def __init__(self, graph: "Graph", kind: Optional[str] = None) -> None:
        self._graph = graph
        self.kind   = kind

    def _eval(self, graph: "Graph") -> set[str]:
        if self.kind:
            return {n.name for n in graph._nodes.values() if n.kind == self.kind}
        return set(graph._nodes.keys())

    def __repr__(self) -> str:
        return f"ContextAll({self.kind or '*'})"


# ── Composite nodes ───────────────────────────────────────────

class ContextUnion(ContextExpression):
    """a ∪ b — members in a OR b (or both)."""

    def __init__(self, a: ContextExpression, b: ContextExpression) -> None:
        self._a     = a
        self._b     = b
        self._graph = a._graph

    def _eval(self, graph: "Graph") -> set[str]:
        return self._a._eval(graph) | self._b._eval(graph)

    def __repr__(self) -> str:
        return f"({self._a!r} ∪ {self._b!r})"

    def explain(self, indent: int = 0) -> str:
        pad = "  " * indent
        return (f"{pad}Union\n"
                f"{self._a.explain(indent+1)}\n"
                f"{self._b.explain(indent+1)}")


class ContextIntersection(ContextExpression):
    """a ∩ b — members in BOTH a AND b."""

    def __init__(self, a: ContextExpression, b: ContextExpression) -> None:
        self._a     = a
        self._b     = b
        self._graph = a._graph

    def _eval(self, graph: "Graph") -> set[str]:
        return self._a._eval(graph) & self._b._eval(graph)

    def __repr__(self) -> str:
        return f"({self._a!r} ∩ {self._b!r})"

    def explain(self, indent: int = 0) -> str:
        pad = "  " * indent
        return (f"{pad}Intersection\n"
                f"{self._a.explain(indent+1)}\n"
                f"{self._b.explain(indent+1)}")


class ContextDifference(ContextExpression):
    """a \\ b — members in a but NOT in b."""

    def __init__(self, a: ContextExpression, b: ContextExpression) -> None:
        self._a     = a
        self._b     = b
        self._graph = a._graph

    def _eval(self, graph: "Graph") -> set[str]:
        return self._a._eval(graph) - self._b._eval(graph)

    def __repr__(self) -> str:
        return f"({self._a!r} \\ {self._b!r})"

    def explain(self, indent: int = 0) -> str:
        pad = "  " * indent
        return (f"{pad}Difference\n"
                f"{self._a.explain(indent+1)}\n"
                f"{self._b.explain(indent+1)}")


class ContextComplement(ContextExpression):
    """
    NOT a — everything in the universe that isn't in a.

    The universe defaults to ContextAll (every node in the graph).
    You can restrict it: ContextComplement(a, b)  means  b \\ a.
    """

    def __init__(self, a: ContextExpression, universe: ContextExpression) -> None:
        self._a       = a
        self._universe = universe
        self._graph   = a._graph

    def _eval(self, graph: "Graph") -> set[str]:
        return self._universe._eval(graph) - self._a._eval(graph)

    def __repr__(self) -> str:
        return f"(¬{self._a!r})"

    def explain(self, indent: int = 0) -> str:
        pad = "  " * indent
        return (f"{pad}Complement\n"
                f"{self._a.explain(indent+1)}\n"
                f"{self._universe.explain(indent+1)}")


class ContextFilter(ContextExpression):
    """Filter members of an expression by a predicate on Node objects."""

    def __init__(self, base: ContextExpression, pred: Callable[["Node"], bool]) -> None:
        self._base  = base
        self._pred  = pred
        self._graph = base._graph

    def _eval(self, graph: "Graph") -> set[str]:
        names = self._base._eval(graph)
        return {n for n in names
                if (node := graph.get_node(n)) and self._pred(node)}

    def __repr__(self) -> str:
        return f"Filter({self._base!r})"


# ── Helper ────────────────────────────────────────────────────

def _coerce(x: "str | ContextExpression", graph: "Graph") -> ContextExpression:
    """Allow passing a context name string wherever a ContextExpression is expected."""
    if isinstance(x, str):
        return ContextReference(x, graph)
    return x
