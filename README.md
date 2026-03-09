# graph_based_namespaces — Graph-based namespaces with OCaml-style modules for Python

A Python library that gives you OCaml-style module semantics — signatures,
functors, `open`, qualified access, and context algebra — backed by a live
program graph that tracks every import, definition, call, and membership edge.

```
pip install graph_based_namespaces   # (or: pip install -e . from source)
```

---

## Quick start

```python
from graph_based_namespaces import Signature, Module, functor, open_module, namespace

# 1. Define a signature (like an OCaml .mli / module type)
class MathSignature(Signature):
    sqrt:  callable
    floor: callable
    pi:    float

# 2. Load a module sealed against the signature
Math = Module("math", signature=MathSignature)
Math.sqrt(16)       # → 4.0
Math.floor(3.7)     # → 3
Math.pi             # → 3.14159…
Math.gcd            # → AttributeError — not in signature, hidden

# 3. OCaml-style open — inject into current namespace
open_module("math", globals())
print(sqrt(9))      # → 3.0  (now in scope)

# 4. Qualified access always works
Math2 = namespace.ocaml_import("math", alias="Math2")
Math2.sqrt(25)      # → 5.0
```

---

## Signatures (`Signature`)

A `Signature` is an explicit public interface, like an OCaml `module type` or `.mli` file.

```python
from graph_based_namespaces import Signature, SignatureViolation

class OrdSignature(Signature):
    compare: callable   # (a, b) -> int

class CollectionSignature(Signature):
    empty:   list
    add:     callable
    member:  callable
```

- Only annotated names are exposed — everything else is hidden.
- Type annotations are runtime-checked (`callable`, `int`, `float`, …).
- Signatures compose via inheritance.

```python
class ExtendedMathSignature(MathSignature):   # inherits sqrt, floor, pi
    ceil: callable
```

---

## Modules (`Module`)

```python
from graph_based_namespaces import Module

# From a Python module path
m = Module("os.path")
m.join("/usr", "local")

# Sealed against a signature
m = Module("math", signature=MathSignature)

# From a plain dict (no file needed)
m = Module.from_dict("MyMath", {
    "add": lambda a, b: a + b,
    "PI":  3.14159,
})
m.add(1, 2)   # → 3
m["PI"]       # → 3.14159
```

Private names (`_*`) are always hidden regardless of signature.

---

## `open_module` — OCaml-style `open`

```python
from graph_based_namespaces import open_module

open_module("math", globals())      # like OCaml: open Math
print(sqrt(4))   # → 2.0

# With a signature (only signature members are injected)
class S(Signature):
    sqrt: callable

open_module("math", globals(), signature=S)
# sqrt is in scope; floor, pi, etc. are not
```

---

## Functors — modules parameterised by modules

OCaml:
```ocaml
module MakeSet (Ord : ORDERED_TYPE) = struct … end
```

graph_based_namespaces:
```python
from graph_based_namespaces import functor, Signature, Module

class OrdSignature(Signature):
    compare: callable

class SetSignature(Signature):
    empty:   list
    add:     callable
    member:  callable

@functor(input_signature=OrdSignature, output_signature=SetSignature)
def MakeSet(Ord):
    empty = []
    def add(s, x):
        return s + [x] if x not in s else s
    def member(s, x):
        return x in s
    return {"empty": empty, "add": add, "member": member}

IntOrd  = Module.from_dict("IntOrd",  {"compare": lambda a, b: a - b})
StrOrd  = Module.from_dict("StrOrd",  {"compare": lambda a, b: (a > b) - (a < b)})

IntSet  = MakeSet(IntOrd,  name="IntSet")
StrSet  = MakeSet(StrOrd,  name="StrSet")

s = IntSet.add(IntSet.empty, 5)
s = IntSet.add(s, 10)
IntSet.member(s, 5)   # → True
```

Functors validate input modules against `input_signature` and output dicts
against `output_signature`. All instances are tracked in the program graph.

---

## Graph contexts — semantic regions

Beyond individual modules, you can organise definitions into **named
semantic regions** that overlap freely (same node, multiple contexts):

```python
from graph_based_namespaces import namespace

# Create contexts
algo  = namespace.context("Algorithm")
arrs  = namespace.context("Arrays")

# Register functions in multiple contexts
algo.add(sorted, "sort")
algo.add(lambda xs, x: x in xs, "search")
arrs.add(sorted, "sort")   # same node — no duplication
arrs.add(map,    "map")

# Context algebra
sorting = namespace.intersection("Algorithm", "Arrays", name="Sorting")
# sorting.members() → [sort]  (the only shared member)

all_ops = namespace.union("Algorithm", "Arrays", name="AllOps")
safe    = namespace.difference("Arrays", "Sorting", name="SafeArrays")
# SafeArrays has map but not sort
```

### Morphisms

```python
m = namespace.morphism(
    "SqlToFP",
    source="SQL", target="Functional",
    mapping={"select": "map", "where_": "filter", "fold": "reduce"},
)
m.apply("select")   # → the "map" function from Functional context
```

### Active context resolution

```python
with namespace.active("Algorithm", "Arrays"):
    fn = namespace.resolve("sort")   # unambiguous → returns the function
    # if same name exists in both active contexts → NameError with hint
```

---

## `smart_import` — drop-in replacement

`smart_import` is an enhanced version of the original `python-smart-imports`
function. It solves the script-vs-package path problem and adds graph tracking,
signature enforcement, aliasing, and optional open.

```python
from graph_based_namespaces import smart_import

# Basic — works whether run as script or package
helpers = smart_import("myproject.utils.helpers")
helpers.some_function()

# With signature
helpers = smart_import("myproject.utils.helpers", signature=HelpersSignature)

# Alias
H = smart_import("myproject.utils.helpers", alias="H")

# Open into current namespace
smart_import("math", open_=True, caller_ns=globals())
print(sqrt(16))   # now in scope
```

---

## The program graph

Every import, definition, call, and context membership is a node or edge
in the underlying `Graph`. You can query it directly:

```python
g = namespace.graph

# What contexts does "sort" belong to?
g.contexts_of("sort")

# What does "mymod.compute" call?
g.callees_of("mymod.compute")

# Transitive dependencies
g.transitive_deps("myapp.main")

# Unused functions (defined but never called)
g.find_unused()

# Analyse source code directly
g.analyse_source(open("myfile.py").read(), "myfile")

# Print the whole graph
g.print_graph()
print(namespace.summary())
```

---

## Architecture

```
graph_based_namespaces/
├── __init__.py      — public API
├── graph.py         — directed labelled program graph (nodes + edges)
├── signature.py     — Signature metaclass, SignatureViolation, runtime type checking
├── module.py        — Module: sealed, export-filtered namespace objects
├── functor.py       — @functor decorator: module factories
├── namespace.py     — Namespace, GraphContext, Morphism, open_module
└── smart.py         — smart_import: graph-aware path-fixing importer
```

### Three levels of "context"

| Level | Name | What it contains | Lives in |
|---|---|---|---|
| Outermost | **Graph context** | Definition references (GRefs / nodes) | `CoreEnv` graph store |
| Middle | **Graded context Γ** | Variable bindings with resource grades | Type checker `Ctx` stack |
| Innermost | **Local typing context** | Lambda-bound De Bruijn variables | Elaborator, gone after elab |

The graph context is about *organisation*. The graded context is about
*resource discipline*. They are orthogonal and compose cleanly.

---

## Requirements

- Python 3.10+
- No external dependencies

## Running tests

```bash
python tests/test_graph_based_namespaces.py
# 42 passed, 0 failed
```
