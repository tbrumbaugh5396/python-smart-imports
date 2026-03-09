"""
graph_based_namespaces — Graph-based namespace system with OCaml-style module semantics.

Public API:
    Signature    — define a module signature (interface)
    Module       — create a signature-enforced module
    functor      — create a module factory (OCaml functor)
    open_module  — inject a module's exports into a namespace
    namespace    — the global graph namespace instance
    Graph        — the underlying program graph
"""
from graph_based_namespaces.graph        import Graph
from graph_based_namespaces.signature    import Signature, SignatureViolation
from graph_based_namespaces.module       import Module, ModuleError
from graph_based_namespaces.functor      import functor
from graph_based_namespaces.namespace    import open_module, namespace
from graph_based_namespaces.smart_import import smart_import

__all__ = [
    "Graph", "Signature", "SignatureViolation",
    "Module", "ModuleError",
    "functor",
    "open_module", "namespace",
    "smart_import",
]
__version__ = "2.0.0"
