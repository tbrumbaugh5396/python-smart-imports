"""
lazy_algebra.py — Lazy context algebra examples.

Demonstrates that expressions are descriptions, not snapshots —
they re-evaluate against the current graph every time .members()
is called, so nodes added *after* an expression is built are
automatically included.

Run with:
    python3 lazy_algebra.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "source"))

from graph_based_namespaces.ns import Namespace

ns = Namespace()
g  = ns.graph

SEP = "─" * 58

def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")

def show(expr, label):
    members = sorted(n.name for n in expr.members(kind="function"))
    print(f"  {label:30s} = {members}")


# ── Register functions and contexts ───────────────────────────

def double(x):   return x * 2
def triple(x):   return x * 3
def square(x):   return x * x
def negate(x):   return -x
def absolute(x): return abs(x)

for name, fn in [("double",double),("triple",triple),("square",square),
                 ("negate",negate),("absolute",absolute)]:
    g.add_node(name, "function", value=fn)

ns.context("A")
for name in ["double","triple","square"]:
    g.add_to_context(name, "A")

ns.context("B")
for name in ["double","negate","absolute"]:
    g.add_to_context(name, "B")


# ══════════════════════════════════════════════════════════════
# 1. Build expressions — nothing computed yet
# ══════════════════════════════════════════════════════════════
section("1. Build the expression tree (no evaluation yet)")

a     = ns.expr("A")
b     = ns.expr("B")

a_and_b   = a & b           # ContextIntersection
a_or_b    = a | b           # ContextUnion
a_minus_b = a - b           # ContextDifference
b_minus_a = b - a           # ContextDifference
not_a     = ~a              # ContextComplement(A, ContextAll)
not_a_in_b = ns.complement("A", within="B")   # B \ A, explicit universe

print(f"  a_and_b   = {a_and_b}")
print(f"  a_or_b    = {a_or_b}")
print(f"  a_minus_b = {a_minus_b}")
print(f"  not_a     = {not_a}")
print(f"  (nothing evaluated yet — just expression objects)")


# ══════════════════════════════════════════════════════════════
# 2. Evaluate — .members() triggers computation
# ══════════════════════════════════════════════════════════════
section("2. Evaluate with .members()")

show(a,           "A")
show(b,           "B")
show(a_and_b,     "A ∩ B")
show(a_or_b,      "A ∪ B")
show(a_minus_b,   "A \\ B")
show(b_minus_a,   "B \\ A")
show(not_a_in_b,  "NOT A  (within=B)")
show(not_a,       "NOT A  (within=all)")


# ══════════════════════════════════════════════════════════════
# 3. Lazy means: new nodes appear automatically
# ══════════════════════════════════════════════════════════════
section("3. Laziness — add a node AFTER building the expression")

print("  Before adding 'halve':")
show(not_a,       "NOT A (before)")

# Add a new function to the graph AFTER not_a was built
def halve(x): return x / 2
g.add_node("halve", "function", value=halve)
# halve is not in A, so it should appear in NOT A automatically

print("\n  After adding 'halve' (expression unchanged):")
show(not_a,       "NOT A (after)")
print("  'halve' appeared without rebuilding the expression ✓")


# ══════════════════════════════════════════════════════════════
# 4. Operator chaining — compose freely before evaluating
# ══════════════════════════════════════════════════════════════
section("4. Chained composition")

# (A ∩ B) | (B \ A) — should equal B
expr = (a & b) | (b - a)
show(expr,  "(A ∩ B) ∪ (B \\ A)  should = B")
show(b,     "B (for comparison)  ")

# NOT (A ∩ B) — complement of the intersection
not_intersection = ~(a & b)
show(not_intersection, "NOT (A ∩ B)")

# A ∩ NOT B — same as A \ B
a_and_not_b = a & ~b
show(a_and_not_b,  "A ∩ (NOT B)  should = A \\ B")
show(a_minus_b,    "A \\ B (for comparison)   ")


# ══════════════════════════════════════════════════════════════
# 5. Filter — refine an expression with a predicate
# ══════════════════════════════════════════════════════════════
section("5. Filter — sub-select by node metadata")

# Only functions whose value doubles its input (just demonstrating the API)
doubles_input = (a | b).filter(
    lambda node: node.meta.get("value") is not None
                 and node.meta["value"](3) == 6
)
show(doubles_input, "x(3)==6 filter on A∪B")


# ══════════════════════════════════════════════════════════════
# 6. Resolve — call a function through a lazy expression
# ══════════════════════════════════════════════════════════════
section("6. Resolve — call through the expression")

val = (a & b).resolve("double")
print(f"  (A ∩ B).resolve('double')(5) = {val(5)}")

val_ab = (a | b).resolve("negate")
print(f"  (A ∪ B).resolve('negate')(5) = {val_ab(5)}")

# 'triple' is in A but not B — not in intersection
missing = (a & b).resolve("triple")
print(f"  (A ∩ B).resolve('triple')    = {missing}  (not in intersection)")


# ══════════════════════════════════════════════════════════════
# 7. explain() — visualise the expression tree
# ══════════════════════════════════════════════════════════════
section("7. explain() — print the expression tree")

complex_expr = (a & b) | (b - a)
print(complex_expr.explain())


# ══════════════════════════════════════════════════════════════
# 8. NOT A: snapshot vs lazy comparison
# ══════════════════════════════════════════════════════════════
section("8. NOT A — snapshot (wrong) vs lazy (correct)")

# Eager/snapshot — captures state NOW, misses future nodes
snapshot_not_a = set(
    n.name for n in g.nodes("function")
    if n.name not in {m.name for m in ns.context("A").members()}
)

# Lazy — re-evaluates on every call
lazy_not_a = ~a

def cube(x): return x ** 3
g.add_node("cube", "function", value=cube)

print(f"  snapshot NOT A  = {sorted(snapshot_not_a)}  ← 'cube' missing")
print(f"  lazy NOT A      = {sorted(n.name for n in lazy_not_a.members(kind='function'))}  ← 'cube' included ✓")

print(f"\n{SEP}")
print("  All lazy algebra examples completed ✓")
print(SEP)
