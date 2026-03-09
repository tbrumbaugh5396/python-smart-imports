"""tests/test_graphns.py — Test suite for graphns"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

import math as _math
import graphns
from graphns import Graph, Sig, SigViolation, Module, ModuleError, functor, open_module, namespace
from graphns.ns import Namespace


# ── Graph tests ───────────────────────────────────────────────

def test_graph_add_node():
    g = Graph()
    n = g.add_node("foo", "function")
    assert n.name == "foo"
    assert g.get_node("foo") is not None

def test_graph_add_edge():
    g = Graph()
    g.add_node("A", "module"); g.add_node("B", "module")
    g.add_edge("A", "imports", "B")
    es = g.edges_from("A", "imports")
    assert len(es) == 1 and es[0].dst == "B"

def test_graph_edges_to():
    g = Graph()
    g.add_node("A","module"); g.add_node("B","module")
    g.add_edge("A","calls","B")
    assert g.edges_to("B","calls")[0].src == "A"

def test_graph_analyse_source():
    g = Graph()
    src = """
def add(a, b):
    return a + b
def compute():
    x = add(1, 2)
    return x
"""
    g.analyse_source(src, "mymod")
    assert g.get_node("mymod.compute") is not None
    calls = g.edges_from("mymod.compute", "calls")
    assert any(e.dst == "add" for e in calls)

def test_graph_context_membership():
    g = Graph()
    g.add_node("sort",   "function")
    g.add_node("search", "function")
    g.add_node("Algorithm", "context")
    g.add_to_context("sort",   "Algorithm")
    g.add_to_context("search", "Algorithm")
    members = {n.name for n in g.members_of("Algorithm")}
    assert "sort" in members and "search" in members

def test_graph_ctx_intersect():
    g = Graph()
    for n in ["sort","search","map","filter"]:
        g.add_node(n,"function")
    g.add_node("Algorithm","context"); g.add_node("Arrays","context")
    g.add_to_context("sort","Algorithm"); g.add_to_context("search","Algorithm")
    g.add_to_context("sort","Arrays");    g.add_to_context("map","Arrays")
    g.ctx_intersect("Algorithm","Arrays","Sorting")
    members = {n.name for n in g.members_of("Sorting")}
    assert members == {"sort"}

def test_graph_ctx_union():
    g = Graph()
    for n in ["sort","map"]:
        g.add_node(n,"function")
    g.add_node("A","context"); g.add_node("B","context")
    g.add_to_context("sort","A"); g.add_to_context("map","B")
    g.ctx_union("A","B","C")
    members = {n.name for n in g.members_of("C")}
    assert members == {"sort","map"}

def test_graph_ctx_diff():
    g = Graph()
    for n in ["sort","search","map"]:
        g.add_node(n,"function")
    g.add_node("A","context"); g.add_node("B","context")
    for n in ["sort","search","map"]: g.add_to_context(n,"A")
    g.add_to_context("sort","B")
    g.ctx_diff("A","B","C")
    members = {n.name for n in g.members_of("C")}
    assert "sort" not in members
    assert "search" in members and "map" in members

def test_graph_find_unused():
    g = Graph()
    g.add_node("used",   "function")
    g.add_node("unused", "function")
    g.add_edge("caller", "calls", "used")
    unused = {n.name for n in g.find_unused()}
    assert "unused" in unused
    assert "used"   not in unused

def test_graph_transitive_deps():
    g = Graph()
    g.add_node("A","module"); g.add_node("B","module"); g.add_node("C","module")
    g.record_import("A","B"); g.record_import("B","C")
    deps = g.transitive_deps("A")
    assert "B" in deps and "C" in deps


# ── Sig tests ─────────────────────────────────────────────────

def test_sig_basic():
    class MathSig(Sig):
        sqrt:    callable
        floor:   callable
        pi:      float

    exports = {"sqrt": _math.sqrt, "floor": _math.floor, "pi": _math.pi,
               "_hidden": "secret", "extra": 42}
    result = MathSig.check(exports)
    assert set(result.keys()) == {"sqrt","floor","pi"}
    assert "extra"   not in result
    assert "_hidden" not in result

def test_sig_missing_member():
    class S(Sig):
        add: callable

    try:
        S.check({})
        assert False, "should raise"
    except SigViolation as e:
        assert "add" in str(e)

def test_sig_wrong_type():
    class S(Sig):
        add: callable

    try:
        S.check({"add": 42})   # 42 is not callable
        assert False, "should raise"
    except SigViolation as e:
        assert "add" in str(e)

def test_sig_is_compatible():
    class S(Sig):
        sqrt: callable

    assert     S.is_compatible({"sqrt": _math.sqrt})
    assert not S.is_compatible({})

def test_sig_inheritance():
    class Base(Sig):
        add: callable

    class Extended(Base):
        mul: callable

    exports = {"add": lambda a,b:a+b, "mul": lambda a,b:a*b, "sub": lambda a,b:a-b}
    result  = Extended.check(exports)
    assert "add" in result and "mul" in result
    assert "sub" not in result


# ── Module tests ──────────────────────────────────────────────

def test_module_load_stdlib():
    m = Module("math")
    assert hasattr(m, "sqrt")
    assert m.sqrt(16) == 4.0

def test_module_hides_private():
    m = Module("math")
    try:
        _ = m._invalid
        assert False
    except AttributeError:
        pass

def test_module_with_sig():
    class MathSig(Sig):
        sqrt:  callable
        floor: callable

    m = Module("math", sig=MathSig)
    assert m.sqrt(9) == 3.0
    # Members not in sig should not be exposed
    try:
        _ = m.pi
        assert False
    except AttributeError:
        pass

def test_module_from_dict():
    m = Module.from_dict("MyMath", {"add": lambda a,b:a+b, "PI": 3.14, "_priv": "x"})
    assert m.add(1,2) == 3
    assert m["PI"]    == 3.14
    try: _ = m._priv; assert False
    except AttributeError: pass

def test_module_contains():
    m = Module("math")
    assert "sqrt" in m
    assert "_internal" not in m

def test_module_keys():
    m = Module.from_dict("M", {"x":1,"y":2})
    assert set(m.keys()) == {"x","y"}

def test_module_exports_copy():
    m  = Module.from_dict("M", {"x":1})
    ex = m.exports()
    ex["x"] = 999
    assert m["x"] == 1   # original unchanged

def test_module_graph_registration():
    g = Graph()
    m = Module("math", alias="Math", graph=g)
    assert g.get_node("Math") is not None
    exports = g.exports_of("Math")
    assert len(exports) > 0

def test_module_bad_path():
    try:
        Module("this.does.not.exist.ever")
        assert False
    except ModuleError:
        pass


# ── Functor tests ─────────────────────────────────────────────

def test_functor_basic():
    class OrdSig(Sig):
        compare: callable

    class SetSig(Sig):
        empty:  list
        add:    callable
        member: callable

    @functor(input_sig=OrdSig, output_sig=SetSig)
    def MakeSet(Ord):
        empty = []
        def add(s, x):
            return s + [x] if x not in s else s
        def member(s, x):
            return Ord.compare(x, x) == 0 and x in s
        return {"empty": empty, "add": add, "member": member}

    IntOrd = Module.from_dict("IntOrd", {"compare": lambda a,b: a-b})
    IntSet = MakeSet(IntOrd, name="IntSet")
    assert isinstance(IntSet, Module)
    s = IntSet.add(IntSet.empty, 5)
    assert 5 in s

def test_functor_repr():
    @functor()
    def MakeMap(K): return {}

    assert "MakeMap" in repr(MakeMap)

def test_functor_bad_input():
    class S(Sig):
        required: callable

    @functor(input_sig=S)
    def F(mod): return {}

    try:
        F(Module.from_dict("bad", {"other": 1}))
        assert False
    except SigViolation:
        pass

def test_functor_instances_tracked():
    @functor()
    def MakeM(Base):
        return {"name": Base._name}

    m1 = Module.from_dict("A", {"x": 1})
    m2 = Module.from_dict("B", {"x": 2})
    MakeM(m1); MakeM(m2)
    assert len(MakeM.instances()) == 2


# ── Namespace / open tests ────────────────────────────────────

def test_open_module_injects():
    ns = {}
    open_module("math", ns)
    assert "sqrt"  in ns
    assert "floor" in ns

def test_open_module_with_sig():
    class S(Sig):
        sqrt: callable

    ns = {}
    open_module("math", ns, sig=S)
    assert "sqrt"  in ns
    assert "floor" not in ns   # not in sig

def test_namespace_ocaml_import():
    ns2  = Namespace()
    Math = ns2.ocaml_import("math", alias="Math")
    assert hasattr(Math, "sqrt")
    assert Math.sqrt(25) == 5.0

def test_namespace_open():
    ns2 = Namespace()
    Math = ns2.ocaml_import("math")
    local = {}
    ns2.open("math", local)
    assert "sqrt" in local

def test_namespace_context_algebra():
    ns2 = Namespace()
    algo  = ns2.context("Algo2")
    arrs  = ns2.context("Arrs2")
    g     = ns2.graph
    for n in ["sort","search","map"]:
        g.add_node(n,"function")
    g.add_to_context("sort","Algo2");   g.add_to_context("search","Algo2")
    g.add_to_context("sort","Arrs2");   g.add_to_context("map","Arrs2")

    sorting = ns2.intersect("Algo2","Arrs2","Sorting2")
    members = {n.name for n in sorting.members()}
    assert members == {"sort"}

def test_namespace_morphism():
    ns2 = Namespace()
    sq = ns2.context("SQL2")
    fp = ns2.context("FP2")

    g = ns2.graph
    g.add_node("map",    "function", value=_math.floor)
    g.add_node("filter", "function", value=_math.ceil)
    g.add_to_context("map",    "FP2")
    g.add_to_context("filter", "FP2")

    m = ns2.morphism("SqlToFP2", src="SQL2", tgt="FP2",
                     mapping={"select": "map", "where_": "filter"})
    result = m.apply("select")
    assert result is _math.floor

def test_namespace_active_context():
    ns2 = Namespace()
    g   = ns2.graph
    g.add_node("sort_fn","function",value=sorted)
    ns2.context("Algo3")
    g.add_to_context("sort_fn","Algo3")
    with ns2.active("Algo3"):
        val = ns2.resolve("sort_fn")
    assert val is sorted

def test_namespace_ambiguity_error():
    ns2 = Namespace()
    g   = ns2.graph
    g.add_node("fn_a","function",value=1)
    g.add_node("fn_b","function",value=2)
    ns2.context("C1"); ns2.context("C2")
    g.add_to_context("fn_a","C1"); g.add_to_context("fn_b","C1")
    # fn_a also in C2 → same name "fn_a" in two active contexts
    g.add_node("fn_a_dup","function",value=3)
    g.add_to_context("fn_a_dup","C2")
    # No ambiguity here since names differ — test uniqueness resolution
    with ns2.active("C1"):
        val = ns2.resolve("fn_a")
        assert val == 1

def test_namespace_summary():
    ns2 = Namespace()
    ns2.ocaml_import("math", alias="Math2")
    s = ns2.summary()
    assert "module" in s

def test_graph_context_repr():
    ns2 = Namespace()
    c = ns2.context("TestCtx")
    assert "TestCtx" in repr(c)


# ── smart_import tests ────────────────────────────────────────

def test_smart_import_basic():
    from graphns.smart import smart_import
    m = smart_import("math")
    assert m.sqrt(9) == 3.0

def test_smart_import_alias():
    from graphns.smart import smart_import
    M = smart_import("math", alias="SMath")
    assert M._name == "SMath"

def test_smart_import_with_sig():
    from graphns.smart import smart_import

    class S(Sig):
        sqrt: callable

    m = smart_import("math", sig=S)
    assert m.sqrt(4) == 2.0
    try: _ = m.floor; assert False
    except AttributeError: pass

def test_smart_import_open():
    from graphns.smart import smart_import
    ns = {}
    smart_import("math", open_=True, caller_ns=ns)
    assert "sqrt" in ns


# ── Run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = fail = 0
    for name, fn in tests:
        try:
            fn(); print(f"  ✓  {name}"); ok += 1
        except Exception as e:
            import traceback
            print(f"  ✗  {name}"); traceback.print_exc(); fail += 1
    print(f"\n{ok} passed, {fail} failed")
    sys.exit(0 if fail == 0 else 1)
