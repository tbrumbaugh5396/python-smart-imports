"""
examples.py — graphns usage examples

Run with:
    python examples.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from graphns import Sig, Module, functor, open_module, namespace, smart_import
from graphns.ns import Namespace


SEP = "─" * 60

def section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ═══════════════════════════════════════════════════════════════
# 1. Basic Module import — no signature
# ═══════════════════════════════════════════════════════════════
section("1. Basic Module — no signature")

Math = Module("math")

print(f"  Math.sqrt(16)   = {Math.sqrt(16)}")
print(f"  Math.pi         = {Math.pi:.5f}")
print(f"  Math.floor(3.9) = {Math.floor(3.9)}")
print(f"  Math repr       = {Math}")


# ═══════════════════════════════════════════════════════════════
# 2. Module with a Signature (OCaml module type)
# ═══════════════════════════════════════════════════════════════
section("2. Module with Sig — only declared members exposed")

class MathSig(Sig):
    sqrt:  callable
    floor: callable
    ceil:  callable
    pi:    float

SealedMath = Module("math", sig=MathSig)
print(f"  SealedMath.sqrt(25)  = {SealedMath.sqrt(25)}")
print(f"  SealedMath.pi        = {SealedMath.pi:.5f}")
print(f"  Keys exposed         = {SealedMath.keys()}")

# Trying to access something not in the sig raises AttributeError
try:
    _ = SealedMath.gcd
except AttributeError as e:
    print(f"  SealedMath.gcd       → AttributeError (hidden by sig) ✓")


# ═══════════════════════════════════════════════════════════════
# 3. Module from a dict — no file needed
# ═══════════════════════════════════════════════════════════════
section("3. Module.from_dict — inline module definition")

Vectors = Module.from_dict("Vectors", {
    "dot":    lambda u, v: sum(x*y for x,y in zip(u,v)),
    "norm":   lambda v:    sum(x**2 for x in v) ** 0.5,
    "scale":  lambda v, s: [x*s for x in v],
    "_cache": {},      # private — auto-hidden
})

u, v = [1,2,3], [4,5,6]
print(f"  dot([1,2,3],[4,5,6])  = {Vectors.dot(u,v)}")
print(f"  norm([3,4])           = {Vectors.norm([3,4]):.1f}")
print(f"  scale([1,2],3)        = {Vectors.scale([1,2],3)}")
print(f"  '_cache' hidden       = {'_cache' not in Vectors} ✓")


# ═══════════════════════════════════════════════════════════════
# 4. open_module — OCaml-style "open"
# ═══════════════════════════════════════════════════════════════
section("4. open_module — inject symbols into current namespace")

# Open math into a local namespace dict (simulates globals())
local_ns = {}
open_module("math", local_ns)

print(f"  sqrt(49)   via open = {local_ns['sqrt'](49)}")
print(f"  cos(0)     via open = {local_ns['cos'](0)}")

# Open with sig — only declared names land in namespace
class TrigSig(Sig):
    sin: callable
    cos: callable
    tan: callable

trig_ns = {}
open_module("math", trig_ns, sig=TrigSig)
print(f"  Keys after open(sig) = {sorted(trig_ns.keys())}")
print(f"  'sqrt' excluded      = {'sqrt' not in trig_ns} ✓")


# ═══════════════════════════════════════════════════════════════
# 5. namespace.ocaml_import — qualified + aliased import
# ═══════════════════════════════════════════════════════════════
section("5. namespace.ocaml_import — ML-style qualified import")

ns = Namespace()

# Simple import
Os = ns.ocaml_import("os.path", alias="Os")
print(f"  Os.join('a','b') = {Os.join('a','b')}")

# With sig and alias — like: module M : SIG = ...
class OsSig(Sig):
    join:    callable
    exists:  callable
    dirname: callable

OsPath = ns.ocaml_import("os.path", alias="OsPath", sig=OsSig)
print(f"  OsPath keys      = {OsPath.keys()}")
print(f"  OsPath.exists('/') = {OsPath.exists('/')}")

# Import and open in one step
opened_ns = {}
ns.ocaml_import("math", alias="Math", open_=True, caller_ns=opened_ns)
print(f"  After open_, 'sqrt' in ns = {'sqrt' in opened_ns} ✓")


# ═══════════════════════════════════════════════════════════════
# 6. Sig inheritance — composing interfaces
# ═══════════════════════════════════════════════════════════════
section("6. Sig inheritance — composing signatures")

class BaseSig(Sig):
    add: callable
    sub: callable

class ExtendedSig(BaseSig):   # inherits add, sub
    mul: callable
    div: callable

print(f"  BaseSig members    = {BaseSig.members()}")
print(f"  ExtendedSig members = {ExtendedSig.members()}")

ops = Module.from_dict("Ops", {
    "add": lambda a,b: a+b,
    "sub": lambda a,b: a-b,
    "mul": lambda a,b: a*b,
    "div": lambda a,b: a/b,
    "mod": lambda a,b: a%b,   # not in sig — will be hidden
}, sig=ExtendedSig)

print(f"  ops.add(10,3)  = {ops.add(10,3)}")
print(f"  ops.mul(4,5)   = {ops.mul(4,5)}")
print(f"  'mod' hidden   = {'mod' not in ops} ✓")


# ═══════════════════════════════════════════════════════════════
# 7. Functors — modules parameterised by modules
# ═══════════════════════════════════════════════════════════════
section("7. Functors — parameterised module factories")

# Define signatures
class CompareSig(Sig):
    compare: callable   # (a, b) -> -1 | 0 | 1

class SortedListSig(Sig):
    empty:   list
    insert:  callable   # insert(lst, x) -> sorted list
    to_list: callable   # to_list(lst) -> list

# Define the functor
@functor(input_sig=CompareSig, output_sig=SortedListSig)
def MakeSortedList(Ord):
    def insert(lst, x):
        for i, el in enumerate(lst):
            if Ord.compare(x, el) <= 0:
                return lst[:i] + [x] + lst[i:]
        return lst + [x]
    return {
        "empty":   [],
        "insert":  insert,
        "to_list": lambda lst: list(lst),
    }

# Instantiate with different orderings
IntOrd = Module.from_dict("IntOrd",  {"compare": lambda a,b: (a>b)-(a<b)})
RevOrd = Module.from_dict("RevOrd",  {"compare": lambda a,b: (b>a)-(b<a)})

IntList = MakeSortedList(IntOrd, name="IntList")
RevList = MakeSortedList(RevOrd, name="RevList")

# Use IntList
s = IntList.empty
for x in [5, 2, 8, 1, 9, 3]:
    s = IntList.insert(s, x)
print(f"  IntList (asc):  {IntList.to_list(s)}")

# Use RevList
r = RevList.empty
for x in [5, 2, 8, 1, 9, 3]:
    r = RevList.insert(r, x)
print(f"  RevList (desc): {RevList.to_list(r)}")

print(f"  Functor repr:   {MakeSortedList}")
print(f"  Instances:      {[m._name for m in MakeSortedList.instances()]}")


# ═══════════════════════════════════════════════════════════════
# 8. Graph contexts — semantic regions
# ═══════════════════════════════════════════════════════════════
section("8. Graph contexts — semantic regions (∪ ∩ −)")

ns2 = Namespace()
g   = ns2.graph

# Register some functions as nodes with values
import math as _math
for name, val in [("sort",sorted),("search",lambda xs,x:x in xs),
                  ("map",map),("filter",filter),("reduce",None)]:
    g.add_node(name, "function", value=val)

# Assign to contexts
algo = ns2.context("Algorithm")
arrs = ns2.context("Arrays")

for name in ["sort","search"]:
    g.add_to_context(name, "Algorithm")
for name in ["sort","map","filter"]:
    g.add_to_context(name, "Arrays")

print(f"  Algorithm members: {[n.name for n in algo.members()]}")
print(f"  Arrays members:    {[n.name for n in arrs.members()]}")

# Intersection — only what both share
sorting = ns2.intersect("Algorithm","Arrays", name="Sorting")
print(f"  Sorting = Algo ∩ Arrays: {[n.name for n in sorting.members()]}")

# Union — everything from either
all_ops = ns2.union("Algorithm","Arrays", name="AllOps")
print(f"  AllOps  = Algo ∪ Arrays: {sorted(n.name for n in all_ops.members())}")

# Difference — Arrays minus what's in Sorting
safe = ns2.diff("Arrays","Sorting", name="SafeArrays")
print(f"  SafeArrays = Arrays − Sorting: {[n.name for n in safe.members()]}")


# ═══════════════════════════════════════════════════════════════
# 9. Active context resolution
# ═══════════════════════════════════════════════════════════════
section("9. Active context resolution — with namespace.active()")

ns3 = Namespace()
g3  = ns3.graph
g3.add_node("sort_fn",   "function", value=sorted)
g3.add_node("search_fn", "function", value=lambda xs,x: x in xs)
g3.add_node("map_fn",    "function", value=map)

ns3.context("Algo4")
ns3.context("Arr4")
g3.add_to_context("sort_fn",   "Algo4")
g3.add_to_context("search_fn", "Algo4")
g3.add_to_context("sort_fn",   "Arr4")
g3.add_to_context("map_fn",    "Arr4")

# Unambiguous resolution
with ns3.active("Algo4"):
    fn = ns3.resolve("search_fn")
    print(f"  resolve('search_fn') in Algo4 = {fn is not None} ✓")

# Direct context lookup
sort_fn = ns3.context("Algo4").resolve("sort_fn")
print(f"  Algo4.resolve('sort_fn') = {sort_fn is sorted} ✓")


# ═══════════════════════════════════════════════════════════════
# 10. Context morphisms — mapping between domains
# ═══════════════════════════════════════════════════════════════
section("10. Context morphisms — mapping between domains")

ns4 = Namespace()
g4  = ns4.graph

# SQL context
g4.add_node("select", "function", value=lambda tbl,f: list(filter(f,tbl)))
g4.add_node("where_", "function", value=lambda tbl,f: list(filter(f,tbl)))
g4.add_node("fold",   "function", value=lambda tbl,f,z: __import__('functools').reduce(f,tbl,z))
ns4.context("SQL")
for n in ["select","where_","fold"]:
    g4.add_to_context(n, "SQL")

# Functional context
g4.add_node("map_",    "function", value=lambda f,xs: list(map(f,xs)))
g4.add_node("filter_", "function", value=lambda f,xs: list(filter(f,xs)))
g4.add_node("reduce_", "function", value=lambda f,xs,z: __import__('functools').reduce(f,xs,z))
ns4.context("Functional")
for n in ["map_","filter_","reduce_"]:
    g4.add_to_context(n, "Functional")

morph = ns4.morphism("SqlToFP", src="SQL", tgt="Functional",
                     mapping={"select":"map_", "where_":"filter_", "fold":"reduce_"})

map_fn    = morph.apply("select")
filter_fn = morph.apply("where_")
reduce_fn = morph.apply("fold")

data = [1,2,3,4,5,6]
doubled  = map_fn(lambda x: x*2, data)
evens    = filter_fn(lambda x: x%2==0, data)
total    = reduce_fn(lambda a,b: a+b, data, 0)
print(f"  SQL.select → FP.map:    {doubled}")
print(f"  SQL.where_ → FP.filter: {evens}")
print(f"  SQL.fold   → FP.reduce: {total}")


# ═══════════════════════════════════════════════════════════════
# 11. smart_import — drop-in smart_import replacement
# ═══════════════════════════════════════════════════════════════
section("11. smart_import — graph-aware path-fixing import")

# Basic
m = smart_import("os.path")
print(f"  smart_import('os.path').join = {m.join('x','y')}")

# With alias
Json = smart_import("json", alias="Json")
print(f"  Json._name       = {Json._name}")
print(f"  Json.dumps([1,2]) = {Json.dumps([1,2])}")

# With sig
class JsonSig(Sig):
    dumps: callable
    loads: callable

SafeJson = smart_import("json", sig=JsonSig, alias="SafeJson")
print(f"  SafeJson keys    = {SafeJson.keys()}")

# Open into a local dict
local = {}
smart_import("math", open_=True, caller_ns=local)
print(f"  After open_: sqrt(64) = {local['sqrt'](64)}")


# ═══════════════════════════════════════════════════════════════
# 12. Program graph queries
# ═══════════════════════════════════════════════════════════════
section("12. Program graph — queries and analysis")

# Analyse a piece of source code
g5 = namespace.graph
src = '''
import os
import math

def compute(x):
    y = math.sqrt(x)
    z = os.path.join("/tmp", str(y))
    return z

def helper(n):
    return n * 2

def unused_fn():
    return 42
'''
g5.analyse_source(src, "mymodule")

# What does compute call?
calls = g5.callees_of("mymodule.compute")
print(f"  mymodule.compute calls:    {calls}")

# What does mymodule import?
imports = [e.dst for e in g5.edges_from("mymodule","imports")]
print(f"  mymodule imports:          {imports}")

# Unused functions
unused = [n.name for n in g5.find_unused() if "mymodule" in n.name]
print(f"  Unused in mymodule:        {unused}")

# Graph summary
print(f"\n  {namespace.summary()}")

print(f"\n{SEP}")
print("  All examples completed successfully ✓")
print(SEP)
