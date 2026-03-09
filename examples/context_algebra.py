"""
context_algebra.py — Examples of logical/set operations on contexts.

Shows A ∩ B, A ∪ B, A \ B, B \ A, NOT A, and qualified access.

Run with:
    python3 context_algebra.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "source"))

from graph_based_namespaces.namespace import Namespace

ns = Namespace()
g  = ns.graph

SEP = "─" * 55

def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")

def show(ctx_name, label=None):
    label = label or ctx_name
    members = sorted(
        n.name for n in ns.context(ctx_name).members()
        if g.get_node(n.name).kind == "function"   # only show functions
    )
    print(f"  {label:20s} = {members}")
    return members


# ── Define five functions ──────────────────────────────────────

def double(x):   return x * 2
def triple(x):   return x * 3
def square(x):   return x * x
def negate(x):   return -x
def absolute(x): return abs(x)
def negative(x): return (-x if x > 0 else x)

for name, fn in [("double",double),("triple",triple),("square",square),
                 ("negate",negate),("absolute",absolute), ("negative", negative)]:
    g.add_node(name, "function", value=fn)


# ── Assign to two contexts ─────────────────────────────────────
#
#   A = { double, triple, square }   — scaling / arithmetic
#   B = { double, negate, absolute } — sign / magnitude
#
#   double is in BOTH — same node, no duplication

ns.context("A")
for name in ["double","triple","square"]:
    g.add_to_context(name, "A")

ns.context("B")
for name in ["double","negate","absolute"]:
    g.add_to_context(name, "B")

ns.context("C")
g.add_to_context("negative", "C")


section("Starting contexts")
show("A", "A")
show("B", "B")
show("C", "C")

# ══════════════════════════════════════════════════════════════
# A ∩ B  — only what both contexts share
# ══════════════════════════════════════════════════════════════
section("A ∩ B  (intersection — in both A and B)")

# New (lazy, correct)
a_and_b = ns.intersection("A", "B")
a_and_b.members(kind="function")

# Callable through the intersection context
fn = a_and_b.resolve("double")
print(f"\n  (A ∩ B).double(5)  = {fn(5)}")
print(f"  Same object as A.double: {fn is ns.context('A').resolve('double')}")


# ══════════════════════════════════════════════════════════════
# A ∪ B  — everything from either context
# ══════════════════════════════════════════════════════════════
section("A ∪ B  (union — in A or B or both)")

a_or_b = ns.union("A", "B")
a_or_b.members(kind="function")

# Every function is callable through the union
union_context = a_or_b
print(f"\n  (A ∪ B).double(4)   = {union_context.resolve('double')(4)}")
print(f"  (A ∪ B).negate(4)   = {union_context.resolve('negate')(4)}")
print(f"  (A ∪ B).square(4)   = {union_context.resolve('square')(4)}")


# ══════════════════════════════════════════════════════════════
# A \ B  — in A but NOT in B
# ══════════════════════════════════════════════════════════════
section("A \\ B  (difference — in A but not in B)")

a_minus_b = ns.difference("A", "B")
print(a_minus_b.members(kind="function"))


# ══════════════════════════════════════════════════════════════
# B \ A  — in B but NOT in A
# ══════════════════════════════════════════════════════════════
section("B \\ A  (difference — in B but not in A)")

b_minus_a = ns.difference("B", "A")
print(b_minus_a.members(kind="function"))



# ══════════════════════════════════════════════════════════════
# NOT A  — every function not in A
# ══════════════════════════════════════════════════════════════
section("NOT A  (complement — all functions outside A)")

# Collect all function nodes, subtract A's members
all_fns = {n.name for n in g.nodes("function")}
a_fns   = {n.name for n in ns.context("A").members()
           if g.get_node(n.name).kind == "function"}
not_a   = all_fns - a_fns

print(not_a)

ns.context("Not_A")
for name in not_a:
    g.add_to_context(name, "Not_A")

show("Not_A", "NOT A")


# ══════════════════════════════════════════════════════════════
# Qualified access: a.double vs b.double
# ══════════════════════════════════════════════════════════════
section("Qualified access — a.double vs b.double")

a_double = ns.context("A").resolve("double")
b_double = ns.context("B").resolve("double")

print(f"  A.double(5)  = {a_double(5)}")
print(f"  B.double(5)  = {b_double(5)}")
print(f"  Same object? = {a_double is b_double}  ← one node, two paths")

print(f"\n  'double' belongs to: {[n.name for n in g.contexts_of('double')]}")


# ══════════════════════════════════════════════════════════════
# Venn summary
# ══════════════════════════════════════════════════════════════
section("Summary — Venn diagram")
print("""
              ┌── A ∩ B ───┐    
              ┌─────────── B ──────────┐       C 
  ┌───────────┌────────────┐───────────┐ ┌───────────┐
  │  triple   |            |           │ │ negative  |
  │  square   │   double   │  negate   │ └───────────┘
  │           |            |  absolute │
  └───────────└────────────┘───────────┘
  └────────── A ───────────┘                   
                           └───────── NOT A ─────────┘ 
  └────────────── A ∪ B ───────────────┘ 
  A ∩ B        = [double]
  A ∪ B        = [absolute, double, negate, square, triple]
  A \\ B       = [square, triple]
  B \\ A       = [absolute, negate]
  NOT A        = [absolute, negate, negative]
""")
