"""
graph_based_namespaces/functor.py — Module functors (OCaml-style module factories).

A functor is a function from modules to modules.

    OCaml:
        module MakeSet (Ord : ORDERED_TYPE) = struct ... end

    graph_based_namespaces:
        @functor(input_signature=OrdSignature, output_signature=SetSignature)
        def MakeSet(Ord):
            def add(s, x): ...
            def mem(s, x): return Ord.compare(x, x) == 0
            return {"add": add, "mem": mem}

        IntSet = MakeSet(IntOrd)
        IntSet.mem(my_set, 5)

The @functor decorator:
  - validates the input module against input_signature
  - validates the output dict against output_signature
  - wraps the result as a Module
  - records the instantiation in the graph
"""
from __future__ import annotations
from typing import Any, Callable, Optional, Type

from graph_based_namespaces.signature    import Signature, SignatureViolation
from graph_based_namespaces.module       import Module
from graph_based_namespaces.graph        import Graph, NODE_FUNCTOR, NODE_MODULE, REL_INSTANCE


def functor(
    input_signature:  Optional[Type[Signature]] = None,
    output_signature: Optional[Type[Signature]] = None,
    graph:      Optional[Graph]     = None,
) -> Callable:
    """
    Decorator that turns a factory function into an OCaml-style functor.

    The factory function receives one or more Module arguments and
    must return a dict of exports.

    Example:

        @functor(input_signature=OrdSignature, output_signature=SetSignature)
        def MakeSet(Ord):
            ...
            return {"empty": set(), "add": add, "mem": mem}

        IntSet = MakeSet(IntOrd)
    """
    def decorator(fn: Callable) -> "_Functor":
        return _Functor(fn, input_signature, output_signature, graph)
    return decorator


class _Functor:
    """
    A callable that validates its module argument(s), runs the factory,
    validates the output, and returns a sealed Module.
    """

    def __init__(
        self,
        fn:         Callable,
        input_signature:  Optional[Type[Signature]],
        output_signature: Optional[Type[Signature]],
        graph:      Optional[Graph],
    ) -> None:
        self._fn         = fn
        self._input_signature  = input_signature
        self._output_signature = output_signature
        self._graph      = graph
        self.__name__    = fn.__name__
        self.__doc__     = fn.__doc__
        self._instances: list[Module] = []

        if graph is not None:
            graph.add_node(fn.__name__, NODE_FUNCTOR,
                           input_signature  = input_signature.__name__  if input_signature  else None,
                           output_signature = output_signature.__name__ if output_signature else None)

    def __call__(self, *module_args: Any, name: Optional[str] = None) -> Module:
        """
        Apply the functor to one or more modules.

        `name`  — optional name for the resulting module; auto-generated if omitted.
        """
        # Validate input modules
        validated_args = []
        for arg in module_args:
            if isinstance(arg, Module):
                if self._input_signature is not None:
                    # Re-check that the module satisfies input_signature
                    self._input_signature.check(arg.exports())
                validated_args.append(arg)
            elif isinstance(arg, dict):
                if self._input_signature is not None:
                    self._input_signature.check(arg)
                # Wrap bare dict as anonymous module
                validated_args.append(Module.from_dict("<arg>", arg))
            else:
                raise TypeError(
                    f"Functor {self.__name__!r} expects Module arguments, "
                    f"got {type(arg).__name__!r}"
                )

        # Run the factory
        raw = self._fn(*validated_args)
        if not isinstance(raw, dict):
            raise TypeError(
                f"Functor {self.__name__!r} must return a dict of exports, "
                f"got {type(raw).__name__!r}"
            )

        # Generate instance name
        if name is None:
            arg_names = [m._name for m in validated_args]
            name = f"{self.__name__}({', '.join(arg_names)})"

        # Build sealed module from output
        result = Module.from_dict(name, raw, signature=self._output_signature, graph=self._graph)
        self._instances.append(result)

        # Record instantiation in graph
        if self._graph is not None:
            self._graph.add_node(name, NODE_MODULE)
            self._graph.add_edge(self.__name__, REL_INSTANCE, name)
            for arg in validated_args:
                self._graph.add_edge(name, "parameterised_by", arg._name)

        return result

    def instances(self) -> list[Module]:
        """All modules produced by this functor so far."""
        return list(self._instances)

    def __repr__(self) -> str:
        in_s  = self._input_signature.__name__  if self._input_signature  else "any"
        out_s = self._output_signature.__name__ if self._output_signature else "any"
        return f"<Functor {self.__name__!r} ({in_s}) → {out_s}>"
