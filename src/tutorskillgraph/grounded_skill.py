"""Retrieve a teaching move from historical episodes and bind it to the current exercise."""

import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise

import sympy as sp

from .diagnostic_math import Comparison, comparison
from .reason_trials import EXP as OLD
from .reason_trials import RAW, digest, events, read_json, windows

NUMBER = r"-?(?:\d+/\d+|\d+(?:\.\d+)?|\.\d+)"
CLOCK = r"(?:\b(?:noon|midnight)\b|\b\d{1,2}(?::\d\d)?\s*(?:am|pm)\b)"
STAGE_NOUN = re.compile(
    r"\b(?:painters?|pumps?|pipes?|workers?|machines?|project|paint a wall|factory)\b", re.IGNORECASE
)
CHANGE = re.compile(
    r"\b(?:joins?|start(?:s|ed|ing)?|turn(?:s|ed)? on|reassigned|leaves?|stops?|switches|departs?|changes?|is added|develops?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Phase:
    boundary: str
    family: str = "work_stages"
    key: str = "stage"


@lru_cache(maxsize=2048)
def phase(text):
    stem = re.split(r"\boptions:", text, flags=re.IGNORECASE)[0]
    stem = re.sub(r"(?i)\b([ap])\.\s*m\.", r"\1m", stem).replace("$", "")
    if not STAGE_NOUN.search(stem) or not CHANGE.search(stem):
        return None
    if not re.search(
        r"\b(?:per (?:hour|minute)|gallons|hours?|days?|liters?|widgets|square feet)\b",
        stem,
        re.IGNORECASE,
    ):
        return None
    times = list(
        dict.fromkeys(m[0].lower().replace(" ", "") for m in re.finditer(CLOCK, stem, re.IGNORECASE))
    )
    # A second timestamp is only a phase boundary when attached to a change of crew or rate.
    for time in times[1:]:
        for m in re.finditer(CLOCK, stem, re.IGNORECASE):
            if m[0].lower().replace(" ", "") != time:
                continue
            before = re.split(r"[.!?;]", stem[: m.start()])[-1][-120:]
            after = re.split(r"[.!?;]", stem[m.end() :])[0][:75]
            if CHANGE.search(before) or (re.search(r"(?i)\bat\s*$", before) and CHANGE.search(after)):
                return Phase(m[0].strip())
    duration = re.search(
        r"\b(?:for|after)\s+(\d+(?:\.\d+)?|one|two|three|four|five|six|eight)\s+(hours?|days?|minutes?)\b[^.!?]{0,65}?\b(?:after which|leaves?|joins?|stops?|reassigned|turned on|turns on)",
        stem,
        re.IGNORECASE,
    )
    if duration:
        return Phase(f"the end of the first {duration[1]} {duration[2]}")
    return None


def material_for(stem):
    return comparison(stem) or phase(stem)


def math_text(text):
    return (
        text.lower()
        .replace("−", "-")
        .replace("$", "")
        .replace(r"\(", "")
        .replace(r"\)", "")
        .replace("’", "'")
        .replace(r"\times", "*")
        .replace(r"\cdot", "*")
    )


def pairs_mentioned(item, text):
    text = math_text(text)
    names = [str(x) for x in item.names]
    found = []
    if len(names) == 1:
        var = names[0]
        pattern = rf"(?:\b{var}\s*(?:=|equals?|is)\s*|\b(?:try|use|plug in|using|for)\s+(?:the number\s+)?)(?P<num>{NUMBER})(?![\d/])"
        found.extend((m.start(), (sp.Rational(m["num"]),)) for m in re.finditer(pattern, text))
        # A bound is used as a witness only when the learner also states the direction of the comparison.
        for m in re.finditer(
            rf"(?:\b{var}\s*|\b(?:anything|values?)\s+)(>|<|greater than|more than|less than|below|above)\s*(1|0)\b",
            text,
        ):
            point = sp.Rational(m[2]) + (
                sp.Rational(1, 2)
                if m[1] in {">", "greater than", "more than", "above"}
                else -sp.Rational(1, 2)
            )
            found.append((m.start(), (point,)))
    elif len(names) == 2:
        for m in re.finditer(rf"\(\s*({NUMBER})\s*,\s*({NUMBER})\s*\)", text):
            found.append((m.start(), (sp.Rational(m[1]), sp.Rational(m[2]))))
        for a, b in (names, names[::-1]):
            pat = rf"\b{a}\s*=\s*({NUMBER})(?:\s*[,;]\s*|\s+and\s+|\s+){b}\s*=\s*({NUMBER})"
            for m in re.finditer(pat, text):
                vals = (sp.Rational(m[1]), sp.Rational(m[2]))
                found.append((m.start(), vals if a == names[0] else vals[::-1]))
    return sorted({(pos, val) for pos, val in found if all(v.is_finite for v in val)})


def stated_relation(text):
    text = math_text(text)
    if re.search(
        r"\b(?:are|they.re|both|is|be|become|they|get|gives?)\s+(?:the\s+)?(?:same|equal)\b|\ba\s*=\s*b\b",
        text,
    ):
        return "C"
    for a, b in (("a", "b"), ("b", "a")):
        if re.search(
            rf"\b{a}\s*>\s*{b}\b|\b{a}\b\s+(?:(?:is|will|always|be|would|can|could|seems|looks)\s+)*(?:greater|larger|bigger|higher)",
            text,
        ):
            return a.upper()
        if re.search(
            rf"\b{a}\s*<\s*{b}\b|\b{a}\b\s+(?:(?:is|will|always|be|would|can)\s+)*(?:smaller|less|lower)",
            text,
        ):
            return b.upper()
    return ""


def certified_reason(item, words):
    if not isinstance(item, Comparison):
        return False
    if item.family == "constant_powers":
        # Two distinct rewrites to powers of the same base with numerically correct values.
        terms = [
            (int(b), int(p))
            for b, p in re.findall(r"\b(\d{1,3})\s*\^\s*\{?(\d{1,2})\}?", math_text(words))
        ]
        return any(
            a == b and a**p == item.left and b**q == item.right and (p != q or words.count("^") >= 2)
            for i, (a, p) in enumerate(terms)
            for b, q in terms[i + 1 :]
        )
    if item.key != "D":
        return False
    hits = pairs_mentioned(item, words)
    observed = set()
    for i, (offset, values) in enumerate(hits):
        until = hits[i + 1][0] if i + 1 < len(hits) else len(math_text(words))
        relation = item.relation(values)
        if relation and stated_relation(math_text(words)[offset:until]) == relation:
            observed.add(relation)
    if len(item.names) == 2 and item.family == "absolute":
        clauses = re.split(r"\b(?:but|whereas|while|however)|[.;\n]", words.lower())
        for clause in clauses:
            sign = (
                1
                if "same sign" in clause or "both positive" in clause
                else -1
                if "opposite sign" in clause
                else 0
            )
            relation = stated_relation(clause)
            if (
                sign
                and relation
                and any(
                    item.relation((a, b)) == relation
                    for a, b in (
                        (sp.Integer(2), sp.Integer(sign)),
                        (sp.Integer(1), sp.Integer(3 * sign)),
                    )
                )
            ):
                observed.add(relation)
    return len(observed) >= 2


@dataclass
class Turn:
    item: object
    stem: str
    learner: str
    prior_teacher: str
    state: str
    supplied: str


def turn_at(block, index, item):
    """Only the displayed exercise and interactions through this learner event are available."""
    shown, last = block[0], block[index]
    conversation = [
        e for e in block[1 : index + 1] if e["practice_problem_id"] == shown["practice_problem_id"]
    ]
    tutors = [e["content"] for e in conversation if e["event_type"] == "ai_tutor_message"]
    teacher = "\n".join(tutors)
    learner = last["content"] if last["event_type"] == "student_message" else ""
    if not learner:
        for e in reversed(conversation[:-1]):
            if e["event_type"] == "ai_tutor_message":
                break
            if e["event_type"] == "student_message":
                learner = e["content"]
                break
    key_supplied = bool(
        re.search(
            r"\b(?:answer (?:is|was)|correct (?:choice|answer) is)\s*[:* ]*[abcd]\b|"
            r"cannot be determined|relationship is not (?:fixed|determined)|"
            r"(?:remaining|painted|completed|filled|produced)\s+(?:is\s+)?\d+",
            teacher,
            re.IGNORECASE,
        )
    )
    supplied = "tutor_worked" if key_supplied else "no_explicit_solution"
    own_work = "\n".join(e["content"] for e in conversation if e["event_type"] == "student_message")
    if certified_reason(item, learner) or (own_work != learner and certified_reason(item, own_work)):
        state = "proof"
    elif learner and (len(learner.split()) > 3 or re.search(r"[=<>^]|\d.+\d", learner)):
        state = (
            "question"
            if "?" in learner
            and not re.search(r"\b(?:i think|because|i got|since|i tried)\b", learner, re.IGNORECASE)
            else "reason"
        )
    elif last["event_type"] == "practice_answer_submitted":
        state = "correct_choice" if last["is_correct"] == "True" else "wrong_choice"
    else:
        state = "response"
    return Turn(item, shown["content"], learner, teacher, state, supplied)


def grounded_move(turn):
    if turn.state == "proof":
        return "acknowledge_proof"
    if isinstance(turn.item, Phase):
        return "locate_phase"
    if (
        turn.item.family == "powers"
        and turn.item.key == "D"
        and re.search(
            r"(?:larger|bigger|greater|higher)\s+(?:the\s+)?(?:power|exponent)|(?:power|exponent).{0,28}(?:larger|bigger|greater|higher)",
            turn.learner,
            re.IGNORECASE,
        )
    ):
        return "challenge_exponent_shortcut"
    if turn.item.key == "D":
        return "test_cases"
    return "derive_invariant"


def learner_turns(block, item):
    visible = {"ai_tutor_message", "student_message", "practice_answer_submitted"}
    active = [(i, e) for i, e in enumerate(block[1:], 1) if e["event_type"] in visible]
    for (index, event), (_, following) in pairwise(active):
        if event["event_type"] == "ai_tutor_message" or following["event_type"] != "ai_tutor_message":
            continue
        if (
            event["practice_problem_id"] != block[0]["practice_problem_id"]
            or following["practice_problem_id"] != event["practice_problem_id"]
        ):
            continue
        yield event, following, turn_at(block, index, item)


@dataclass(frozen=True)
class Episode:
    session: str
    shown: int
    learner: int
    tutor: int
    family: str
    objective: str
    observation: str
    assistance: str
    move: str
    later: tuple
    parent: str

    def roles(self):
        return (
            ("family", self.family),
            ("objective", self.objective),
            ("observation", self.observation),
            ("assistance", self.assistance),
            ("skill", self.move),
        )


def objective(item):
    return (
        "change_of_rate"
        if isinstance(item, Phase)
        else "variable_order"
        if item.key == "D"
        else "fixed_order"
    )


class GroundedGraph:
    def __init__(self, episodes):
        self.episodes = episodes
        self.incidence = defaultdict(set)
        for i, edge in enumerate(episodes):
            for role in edge.roles():
                self.incidence[role].add(i)

    def retrieve(self, turn, session, *, flat=False):
        query = (
            ("objective", objective(turn.item)),
            ("observation", observation(turn)),
            ("family", turn.item.family),
            ("assistance", turn.supplied),
        )
        # Back off from exact material and speaker history before dropping the observable state.
        for n in (4, 3, 2):
            if flat:
                ids = [i for i, e in enumerate(self.episodes) if all(q in e.roles() for q in query[:n])]
            else:
                ids = sorted(set.intersection(*(self.incidence.get(q, set()) for q in query[:n])))
            found = [self.episodes[i] for i in ids if self.episodes[i].session != session]
            if found:
                return sorted(found, key=lambda e: (not e.later, not e.parent, e.session, e.learner))
        return []


def independent_evidence(block, item):
    """First recorded submission or verified proof before this new item's first tutor reply."""
    for e in block[1:]:
        if e["event_type"] == "ai_tutor_message":
            break
        if e["practice_problem_id"] != block[0]["practice_problem_id"]:
            continue
        if e["event_type"] == "student_message" and certified_reason(item, e["content"]):
            return (block[0]["pos"], e["pos"], "independent_proof")
        if e["event_type"] == "practice_answer_submitted":
            return (block[0]["pos"], e["pos"], "correct" if e["is_correct"] == "True" else "incorrect")
    return ()


def observation(turn):
    if grounded_move(turn) == "challenge_exponent_shortcut":
        return "exponent_size_claim"
    return turn.state


def build_memory():
    episodes = []
    sources = read_json(OLD / "sources.json")["files"]
    parents = {
        (c["session"], event): f"{c['session']}/lesson/{c['old']}/v2"
        for c in read_json(OLD / "cases.json")
        for event in (c["old"], c["probe"])
    }
    for session, expected in sorted(sources.items()):
        if digest(RAW / f"{session}.csv") != expected:
            raise ValueError(f"Historical trajectory changed: {session}")
        lessons = [
            (b, m) for b in windows(events(session)) if (m := material_for(b[0]["content"])) is not None
        ]
        independent = [independent_evidence(b, m) for b, m in lessons]
        for j, (block, item) in enumerate(lessons):
            shown = block[0]
            later = next(
                (
                    independent[k]
                    for k in range(j + 1, len(lessons))
                    if independent[k]
                    and lessons[k][0][0]["concept_id"] == shown["concept_id"]
                    and lessons[k][0][0]["practice_problem_id"] != shown["practice_problem_id"]
                    and lessons[k][1].family == item.family
                ),
                (),
            )
            used = set()
            for learner, tutor, turn in learner_turns(block, item):
                signature = (observation(turn), turn.supplied)
                if signature in used:
                    continue
                used.add(signature)
                episodes.append(
                    Episode(
                        session,
                        block[0]["pos"],
                        learner["pos"],
                        tutor["pos"],
                        item.family,
                        objective(item),
                        observation(turn),
                        turn.supplied,
                        grounded_move(turn),
                        later,
                        parents.get((session, shown["pos"]), ""),
                    )
                )
    return GroundedGraph(episodes)


def example_pair(item, turn, *, target_relation=None):
    used = {v for _, v in pairs_mentioned(item, turn.prior_teacher + "\n" + turn.learner)}
    examples = sorted(
        item.examples, key=lambda pair: (pair[0] in used, len(pair[0]) > 1 and len(set(pair[0])) == 1)
    )
    best = None
    for i, (a, ra) in enumerate(examples):
        for j, (b, rb) in enumerate(examples[i + 1 :], i + 1):
            if ra == rb:
                continue
            # Prefer a reversed ordering to a tie when both are possible; hold other variables fixed.
            rank = (
                int(target_relation is not None and target_relation not in (ra, rb)),
                int(a in used) + int(b in used),
                int("C" in {ra, rb}),
                sum(x != y for x, y in zip(a, b)),
                i + j,
            )
            if best is None or rank < best[0]:
                best = (rank, a, b)
    return (best[1], best[2]) if best else None


def lesson_addition(graph, turn, session, *, flat=False):
    edges = graph.retrieve(turn, session, flat=flat)
    if not edges:
        return "", [], ""
    voters = defaultdict(set)
    for edge in edges:
        voters[edge.move].add(edge.session)
    move = max(sorted(voters), key=lambda m: len(voters[m]))
    evidence = []
    seen = set()
    for e in edges:
        if e.move == move and e.session not in seen:
            evidence.append([e.session, e.shown, e.learner, e.tutor])
            seen.add(e.session)
        if len(evidence) == 3:
            break
    if move == "acknowledge_proof":
        if turn.item.key == "D":
            text = (
                "Check the student's two cases against this problem. If they already establish different "
                "relations, acknowledge exactly what their reasoning establishes and let them move on."
            )
        else:
            text = (
                "Check the learner's common-base derivation against both quantities. If the rewrites "
                "and the resulting comparison are correct, confirm their argument and let them move on."
            )
    elif move == "locate_phase":
        text = (
            f"Use the actual transition at {turn.item.boundary} in this exercise. Find the first step "
            "the learner has yet to do: if the first-stage amount is missing, ask for the work done "
            "by that transition, before the crew or rate changes. If that amount is already given, "
            "build on it and ask for the remaining work or the new rate. Leave the calculation to them."
        )
    elif move == "derive_invariant":
        method = {
            "constant_powers": "rewrite each quantity using a common base",
            "exponential": "rewrite both sides with the same base and compare their exponents",
            "rational": "factor first, identify where the denominator is nonzero, and compare the simplified expressions",
            "absolute": "use the sign restrictions to decide how the absolute values simplify",
        }.get(turn.item.family, "simplify the difference using the stated constraints")
        if r"\sqrt" in turn.stem and turn.item.family != "constant_powers":
            method = "use the principal square root and the sign of its argument before comparing the two sides"
        audit = {"A": "A is greater", "B": "B is greater", "C": "the quantities are equal"}[
            turn.item.key
        ]
        text = (
            f"Algebra check for the tutor: on the defined domain {audit}. The relevant operation is to "
            f"{method}. If the student has not done it, give one entry point and let them complete the "
            "factorization, rewrite, or comparison. If their question or a disputed grade already "
            "names the result, resolve why it follows, then let them progress."
        )
        if turn.item.holes:
            text += (
                f" The printed givens leave {turn.item.names[0]}={', '.join(turn.item.holes)} possible, "
                "where the original denominator vanishes. Distinguish the defined domain from the printed givens."
            )
    else:
        pair = example_pair(turn.item, turn)
        if pair is None:
            return "", evidence, ""
        a, b = (turn.item.format_values(v) for v in pair)
        text = (
            f"Two admissible test cases for the current expressions are ({a}) and ({b}). Use a fresh "
            "case the learner still needs; invite them to evaluate and interpret it before supplying its "
            "result. If their own argument already establishes two relations, acknowledge it and move on."
        )
        if move == "challenge_exponent_shortcut":
            text += (
                " Address their specific claim about exponent size. Have them test its prediction "
                "against a legal counterexample, then revise the claim in their own words."
            )
    intro = (
        "Address the learner's latest message first. Check whether they refer to the displayed exercise "
        "or a different example in the chat. Use this note for the displayed exercise. Credit only work "
        "the learner actually showed. For a bare submission leave them one specific, unfinished step; "
        "when they have justified it, acknowledge that step and move on. "
    )
    return intro + text, evidence, move
