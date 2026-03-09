"""
graph_based_namespaces/smart.py — Upgraded smart_import, now graph-aware.

Drop-in replacement for the original smart_import() from
python-smart-imports.  It handles the script-vs-package path problem
exactly as before, but also:

  - registers the imported module in the program graph
  - supports optional signature enforcement
  - supports open_=True to inject exports into the caller's namespace
  - records the caller → importee edge in the graph
"""
from __future__ import annotations
import importlib
import inspect
import os
import sys
from typing import Any, Optional, Type

from graph_based_namespaces.signature   import Signature
from graph_based_namespaces.graph       import Graph, NODE_MODULE, REL_IMPORTS
from graph_based_namespaces.module      import Module


def smart_import(
    module_path:  str,
    package_root: Optional[str]             = None,
    signature:    Optional[Type[Signature]] = None,
    alias:        Optional[str]             = None,
    open_:        bool                      = False,
    graph:        Optional[Graph]           = None,
    caller_ns:    Optional[dict]            = None,
) -> Module:
    """
    Intelligently import a module whether running as a script or package.

    Solves the classic Python problem:

        # This fails when running as a script:
        from myproject.utils.helpers import foo

        # This always works:
        helpers = smart_import("myproject.utils.helpers")
        helpers.foo()

    Extended features (new in graph_based_namespaces):

        # Signature enforcement:
        helpers = smart_import("myproject.utils.helpers", signature=HelpersSignature)

        # Module aliasing (OCaml style):
        H = smart_import("myproject.utils.helpers", alias="H")

        # Open into current namespace:
        smart_import("math", open_=True, caller_ns=globals())
        print(sqrt(16))

        # Graph tracking:
        helpers = smart_import("myproject.utils.helpers", graph=my_graph)

    Parameters
    ----------
    module_path : str
        Dotted Python module path.
    package_root : str, optional
        Override auto-detected package root.
    signature : Signature subclass, optional
        Signature to enforce; only declared members are exposed.
    alias : str, optional
        Local name for the module.
    open_ : bool
        If True, inject exports into caller_ns.
    graph : Graph, optional
        Program graph to register into.
    caller_ns : dict, optional
        Namespace for open_=True. Auto-detected if None.

    Returns
    -------
    Module
        Sealed module object.
    """
    # ── Auto-detect caller context ────────────────────────────
    frame       = inspect.currentframe()
    caller_frame = frame.f_back if frame else None

    if caller_ns is None and open_ and caller_frame:
        caller_ns = caller_frame.f_globals

    caller_file = caller_frame.f_globals.get("__file__", "") if caller_frame else ""
    caller_name = caller_frame.f_globals.get("__name__", "") if caller_frame else ""
    caller_pkg  = caller_frame.f_globals.get("__package__", None) if caller_frame else None

    # ── Path fixup (original smart_import logic) ──────────────
    if package_root is None and caller_file:
        # Assume package root is one directory above the calling file
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(caller_file)))

    if package_root and package_root not in sys.path:
        # Only add when running as a script (no package context)
        if caller_pkg is None or caller_name == "__main__":
            sys.path.insert(0, package_root)

    # ── Load ──────────────────────────────────────────────────
    from graph_based_namespaces.namespace import namespace as _ns
    active_graph = graph or _ns.graph

    name = alias or module_path
    mod  = Module(module_path, signature=signature, alias=name, graph=active_graph)

    # Record caller → importee edge
    if caller_name and caller_name != "__main__":
        active_graph.add_node(caller_name, NODE_MODULE)
        active_graph.add_edge(caller_name, REL_IMPORTS, module_path)

    # Register in global namespace
    _ns.register(mod)

    # Inject into caller's namespace if requested
    if open_ and caller_ns is not None:
        for k, v in mod.exports().items():
            if not k.startswith("_"):
                caller_ns[k] = v

    return mod
