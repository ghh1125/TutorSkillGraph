"""Construct exact, admissible examples for a small GRE comparison grammar."""

import ast
import itertools
import re
from dataclasses import dataclass
from functools import lru_cache

import sympy as sp

REL = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge, "=": sp.Eq, "!=": sp.Ne}
GRID = tuple(map(sp.Rational, ("1", "2", "-1", "1/2", "-2", "0", "-1/2", "3", "-3", "4", "1/3", "5")))
OPERATIONS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}
ATOMS = {name: sp.Symbol(name, real=True) for name in "abcdefghijklmnopqrstuvwxyz"}
FUNCTIONS = {"abs": sp.Abs, "sqrt": sp.sqrt, "min": sp.Min, "max": sp.Max}


def latex(text):
    text = text.lower().replace("−", "-").replace("²", "^2").replace("³", "^3")
    for old, new in (
        (r"\left", ""),
        (r"\right", ""),
        (r"\cdot", "*"),
        (r"\times", "*"),
        (r"\neq", "!="),
        (r"\ne", "!="),
        (r"\leq", "<="),
        (r"\geq", ">="),
        (r"\le", "<="),
        (r"\ge", ">="),
        ("≠", "!="),
        ("≤", "<="),
        ("≥", ">="),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\,", ""),
        (r"\!", ""),
    ):
        text = text.replace(old, new)
    text = text.replace(r"\(", "").replace(r"\)", "").replace("$", "")
    for _ in range(4):
        text = re.sub(r"\^\{([^{}]+)\}", r"^(\1)", text)
        text = re.sub(r"\\(?:d?frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}", r"((\1)/(\2))", text)
        text = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)
    return text


def expression(text, restrictions):
    text = latex(text).strip()
    if len(text) > 120 or not re.fullmatch(r"[a-z0-9()+*/.,|\^\s-]+", text):
        raise ValueError("Outside arithmetic grammar")
    # Separate consecutive variable names while preserving known function tokens.
    if re.search(r"[a-z]{3,}", re.sub(r"sqrt|abs|min|max", "", text)):
        raise ValueError("Prose in an expression")
    bars = text.split("|")
    if len(bars) % 2 == 0:
        raise ValueError("Unbalanced absolute value")
    text = "".join(f"abs({v})" if i % 2 else v for i, v in enumerate(bars))
    tokens = re.findall(r"sqrt|abs|min|max|[a-z]|\d+(?:\.\d+)?|[()+*/.,^-]", text)
    pieces = []
    for i, token in enumerate(tokens):
        prev = tokens[i - 1] if i else ""
        if (
            i
            and (prev == ")" or prev[0].isdigit() or prev in ATOMS)
            and (token == "(" or token[0].isalpha())
        ):
            pieces.append("*")
        pieces.append("**" if token == "^" else token)

    def convert(node):
        if (
            isinstance(node, ast.Constant)
            and type(node.value) in (int, float)
            and abs(node.value) <= 10000
        ):
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name) and node.id in ATOMS:
            return ATOMS[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = convert(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
            a, b = convert(node.left), convert(node.right)
            if isinstance(node.op, ast.Pow):
                if b.free_symbols:
                    if not (
                        a.is_Integer
                        and 1 <= a <= 200
                        and len(b.free_symbols) == 1
                        and b.is_polynomial()
                        and sp.Poly(b).total_degree() == 1
                        and all(abs(k) <= 64 for k in sp.Poly(b).all_coeffs())
                    ):
                        raise ValueError("Unsupported exponent")
                elif abs(b) > 64:
                    raise ValueError("Unsupported exponent")
            if isinstance(node.op, ast.Div):
                restrictions.append(sp.Ne(b, 0))
            if isinstance(node.op, ast.Pow) and b.is_negative:
                restrictions.append(sp.Ne(a, 0))
            return OPERATIONS[type(node.op)](a, b)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS:
            args = [convert(a) for a in node.args]
            if node.func.id == "sqrt" and len(args) == 1:
                restrictions.append(sp.Ge(args[0], 0))
            return FUNCTIONS[node.func.id](*args)
        raise ValueError("Unsupported arithmetic")

    return convert(ast.parse("".join(pieces), mode="eval").body)


def domain(text):
    text = latex(text).replace("non-zero", "nonzero")
    boilerplate = (
        r"quantitative comparison|compare quantity a (?:and|with|to) quantity b|"
        r"compare(?: the (?:two )?quantities)?|which quantity is greater|"
        r"choose the correct (?:comparison|relationship|qc answer)|select the correct (?:answer|relationship)"
    )
    text = re.sub(rf"\b(?:{boilerplate})\b\s*[.:?]?", " ", text)
    text = re.sub(r"\b(?:given|where|if|such that|let|assume that|suppose that)\b\s*:?", " ", text)
    constraints, integers = [], set()
    descriptor = (
        r"\b([a-z](?:(?:\s*,\s*|\s+and\s+)[a-z])*)\s+(?:is|are)\s+"
        r"(?:(?:a|an|both|two)\s+)?((?:(?:positive|negative|nonzero|distinct|different|real|"
        r"nonnegative|nonpositive)\s+)*)(numbers?|integers?|reals?)\b"
    )

    def describe(m):
        names = [ATOMS[x] for x in re.findall(r"\b[a-z]\b", m[1])]
        words = m[2].split()
        if m[3].startswith("integer"):
            integers.update(names)
        for word, op in (
            ("positive", ">"),
            ("negative", "<"),
            ("nonzero", "!="),
            ("nonnegative", ">="),
            ("nonpositive", "<="),
        ):
            if word in words:
                constraints.extend(REL[op](x, 0) for x in names)
        if "distinct" in words or "different" in words:
            constraints.extend(sp.Ne(x, y) for x, y in itertools.combinations(names, 2))
        return " "

    text = re.sub(descriptor, describe, text)
    text = re.sub(
        r"\b([a-z])\s+is\s+(positive|negative|nonzero)\b",
        lambda m: m[1] + {"positive": ">0", "negative": "<0", "nonzero": "!=0"}[m[2]],
        text,
    )
    for clause in re.split(r"\band\b|[,;\n]", text):
        clause = clause.strip(" \t.:")
        if not clause:
            continue
        parts = re.split(r"(!=|>=|<=|[<>=])", clause)
        if len(parts) < 3:
            raise ValueError("Unparsed domain clause")
        for i in range(1, len(parts), 2):
            constraints.append(
                REL[parts[i]](
                    expression(parts[i - 1], constraints), expression(parts[i + 1], constraints)
                )
            )
    return constraints, integers


@dataclass
class Comparison:
    names: tuple
    left: object
    right: object
    constraints: tuple
    integers: frozenset
    examples: tuple
    key: str
    family: str
    holes: tuple = ()

    def relation(self, values):
        if len(values) != len(self.names):
            return None
        bindings = dict(zip(self.names, values))
        if any(not bindings[x].is_integer for x in self.integers):
            return None
        if any(c.xreplace(bindings) != sp.true for c in self.constraints):
            return None
        a, b = self.left.xreplace(bindings), self.right.xreplace(bindings)
        if a.is_real is not True or b.is_real is not True or not (a.is_finite and b.is_finite):
            return None
        diff = a - b
        return "C" if diff.is_zero else "A" if diff.is_positive else "B" if diff.is_negative else None

    def format_values(self, values):
        return ", ".join(f"{name}={val}" for name, val in zip(self.names, values))


def split_quantities(text):
    text = re.sub(r"\\neq?(?=[^a-zA-Z]|$)", "!=", text.replace("**", "")).replace(r"\n", "\n")
    text = re.split(r"(?i)\boptions\s*:|\bA[.)]\s+Quantity\s+A\s+is\b", text, maxsplit=1)[0]
    labels = list(re.finditer(r"(?i)\bQuantity\s+([AB])\b[ \t]*(?:[:=][ \t]*|(?=\$|\\\(|\n))", text))
    if len(labels) != 2 or tuple(m[1].upper() for m in labels) != ("A", "B"):
        raise ValueError("Missing quantities")
    first, second = labels
    chunks = (text[: first.start()], text[first.end() : second.start()], text[second.end() :])

    def take(s):
        s = s.strip()
        if s.startswith("$"):
            m = re.match(r"(\${1,2})(.+?)\1", s, re.DOTALL)
        elif s.startswith(r"\("):
            m = re.match(r"(\\\()(.+?)\\\)", s, re.DOTALL)
        else:
            m = re.match(r"()([^\n]+)", s)
        if not m:
            raise ValueError("Missing expression")
        tail = re.sub(
            r"(?i)\b(?:compare the two quantities|evaluate the two quantities and select the appropriate statement|which quantity is greater|which is greater)\s*[.?!]?\s*$",
            "",
            s[m.end() :],
        )
        return m[2], tail

    a, a_rest = take(chunks[1])
    b, b_rest = take(chunks[2])
    return a, b, " ".join([chunks[0], a_rest, b_rest]).strip()


@lru_cache(maxsize=4096)
def comparison(text):
    try:
        a, b, given = split_quantities(text)
        constraints, integers = domain(given)
        given_count = len(constraints)
        left, right = expression(a, constraints), expression(b, constraints)
        names = tuple(
            sorted(
                left.free_symbols
                | right.free_symbols
                | set().union(*(c.free_symbols for c in constraints))
                | integers,
                key=str,
            )
        )
        if len(names) > 2 or (not names and not ("^" in a and "^" in b)):
            return None
        fraction = any(
            isinstance(c, sp.Unequality) and c.free_symbols for c in constraints[given_count:]
        )
        exponential = any(
            isinstance(x, sp.Pow) and x.exp.free_symbols
            for expr in (left, right)
            for x in sp.preorder_traversal(expr)
        )
        family = (
            "constant_powers"
            if not names
            else "rational"
            if fraction
            else "exponential"
            if exponential
            else "absolute"
            if "|" in a + b or left.has(sp.Abs) or right.has(sp.Abs)
            else "powers"
            if "^" in a + b
            else "algebra"
        )
        item = Comparison(names, left, right, tuple(constraints), frozenset(integers), (), "", family)
        if fraction and len(names) == 1:
            roots = set()
            for exclusion in constraints[given_count:]:
                if isinstance(exclusion, sp.Unequality) and exclusion.lhs.is_polynomial(names[0]):
                    for root in sp.polys.polytools.ground_roots(exclusion.lhs - exclusion.rhs, names[0]):
                        binding = {names[0]: root}
                        if (not integers or root.is_integer) and all(
                            c.xreplace(binding) == sp.true for c in constraints[:given_count]
                        ):
                            roots.add(str(root))
            item.holes = tuple(sorted(roots))
        examples = []
        seen = set()
        for values in itertools.product(GRID, repeat=len(names)):
            rel = item.relation(values)
            if rel:
                examples.append((values, rel))
                seen.add(rel)
            if len(examples) >= 20 and len(seen) >= 2:
                break
        if not examples:
            return None
        if len(seen) >= 2:
            item.key = "D"
        else:
            # Only symbolic identities or globally strict signs certify a fixed result.
            diff = sp.factor(left - right)
            item.key = (
                "C" if diff.is_zero else "A" if diff.is_positive else "B" if diff.is_negative else ""
            )
            if not item.key and len(names) == 1 and sp.count_ops(diff) <= 18:
                proposed = next(iter(seen))
                opposite = {"A": sp.Le, "B": sp.Ge, "C": sp.Ne}[proposed]
                if sp.reduce_inequalities([*constraints, opposite(diff, 0)], names[0]) == sp.false:
                    item.key = proposed
        item.examples = tuple(examples)
        return item if item.key else None
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError, KeyError, NotImplementedError):
        return None
