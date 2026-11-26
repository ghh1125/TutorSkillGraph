"""Choose a diagnostic comparison using later independent submissions from earlier classes."""

from collections import defaultdict
from dataclasses import dataclass

from .grounded_skill import example_pair, material_for
from .reason_trials import events

RELATIONS = {"A": "A is greater", "B": "B is greater", "C": "the quantities are equal"}


@dataclass(frozen=True)
class Transfer:
    session: str
    lesson: int
    earlier_submission: int
    tutor: int
    later_lesson: int
    first_submission: int
    family: str
    witnessed_relations: str
    answer: str


class TransferHistory:
    def __init__(self, transfers):
        self.transfers = transfers

    @classmethod
    def from_graph(cls, graph):
        latest = {}
        for edge in graph.episodes:
            if edge.later:
                key = (edge.session, *edge.later[:2])
                if key not in latest or edge.tutor > latest[key].tutor:
                    latest[key] = edge

        transfers, classrooms = [], {}
        for (session, shown, pos), edge in sorted(latest.items()):
            if edge.objective != "variable_order":
                continue
            if session not in classrooms:
                classrooms[session] = {row["pos"]: row for row in events(session)}
            rows = classrooms[session]
            before, after = rows[edge.learner], rows[pos]
            if (before["submitted_answer"], before["is_correct"]) != ("D", "True"):
                continue
            item = material_for(rows[shown]["content"])
            answer = after["submitted_answer"]
            if (
                item.key != "D"
                or after["event_type"] != "practice_answer_submitted"
                or answer not in {"A", "B", "C", "D"}
                or after["is_correct"] != ("True" if answer == "D" else "False")
            ):
                continue
            relations = "".join(sorted({r for _, r in item.examples}))
            transfers.append(
                Transfer(
                    session,
                    edge.shown,
                    edge.learner,
                    edge.tutor,
                    shown,
                    pos,
                    item.family,
                    relations,
                    answer,
                )
            )
        return cls(transfers)

    def revise(self, turn, submission, session):
        if turn.item.key != "D" or turn.state not in {"correct_choice", "wrong_choice"}:
            return None
        if submission not in {"A", "B", "C", "D"}:
            return None
        available = "".join(sorted({r for _, r in turn.item.examples}))
        targets = set(available) if submission == "D" else {submission}
        candidates = [
            row
            for row in self.transfers
            if row.session != session and row.answer != "D" and row.answer in targets
        ]
        if not candidates:
            return None

        # Prefer the same exercise family and attainable comparisons. A student votes once per option.
        def similarity(row):
            return (row.family == turn.item.family, row.witnessed_relations == available)

        best = max(map(similarity, candidates))
        votes = defaultdict(set)
        matched = [row for row in candidates if similarity(row) == best]
        for row in matched:
            votes[row.answer].add(row.session)
        target = max(sorted(votes), key=lambda choice: len(votes[choice]))
        pair = example_pair(turn.item, turn, target_relation=target)
        if pair is None:
            return None
        first, second = pair
        if turn.item.relation(second) == target:
            first, second = second, first
        first_text, second_text = [turn.item.format_values(values) for values in (first, second)]
        r1, r2 = [turn.item.relation(values) for values in (first, second)]
        checks = (
            f"Private checks for the displayed problem: at ({first_text}), {RELATIONS[r1]}; "
            f"at ({second_text}), {RELATIONS[r2]}. Both inputs satisfy the givens. "
        )
        if submission == "D":
            focus = (
                "The student submitted D. Their choice alone leaves open whether they can produce "
                "the contrasting case themselves. Ask for a legal case that changes the initial "
                f"comparison '{RELATIONS[target]}'. If they need a starting point, offer the "
                "first input without its result. Accept a complete algebraic argument as well."
            )
        else:
            focus = (
                f"The learner submitted {submission} ({RELATIONS[submission]}). Have them "
                f"test that specific conjecture at ({second_text}) and compare the two values "
                "themselves. If one relationship is already established, ask only for the missing "
                "comparison. Keep the result for feedback after their attempt."
            )
        note = (
            "Respond to the learner's current exercise and any outstanding question. "
            + checks
            + focus
            + " If their visible reasoning already settles it, confirm and move on."
        )
        trace = {
            "hypothesis": target,
            "basis": "observed_choice" if submission != "D" else "earlier_independent_choices",
            "support": [
                [r.session, r.earlier_submission, r.first_submission]
                for r in matched
                if r.answer == target
            ],
            "witnesses": [[first_text, r1], [second_text, r2]],
        }
        return note, trace
