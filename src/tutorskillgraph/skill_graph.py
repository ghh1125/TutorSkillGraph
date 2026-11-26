"""Versioned teaching moves built from completed lessons, indexed by typed incidences."""

from collections import defaultdict
from dataclasses import asdict, dataclass

from .reason_trials import EXP, comparison_case, read_json


@dataclass(frozen=True)
class LessonVersion:
    id: str
    parent: str | None
    source_session: str
    skill: str
    material: str
    observation: str
    learner_step: str
    action: str
    instruction: str
    evidence: dict

    def incidences(self):
        return (("skill", self.skill), ("material", self.material),
                ("observation", self.observation), ("learner_step", self.learner_step),
                ("source", self.source_session))


class SkillGraph:
    def __init__(self, versions):
        self.versions = {v.id: v for v in versions}
        self.index = defaultdict(set)
        for version in self.versions.values():
            for node in version.incidences():
                self.index[node].add(version.id)

    def retrieve(self, *, student, skill, material, observation):
        ids = (self.index.get(("skill", skill), set())
               & self.index.get(("material", material), set())
               & self.index.get(("observation", observation), set()))
        return [self.versions[i] for i in sorted(ids)
                if self.versions[i].parent and self.versions[i].source_session != student]

    def as_record(self):
        return {"nodes": [{"role": r, "value": v, "incident_versions": sorted(ids)}
                          for (r, v), ids in sorted(self.index.items())],
                "lesson_versions": [asdict(v) for v in self.versions.values()]}


def build_graph():
    cases = read_json(EXP / "cases.json")
    tags = read_json(EXP / "skill_tags.json")
    sources = read_json(EXP / "sources.json")
    if set(tags) != {c["session"] for c in cases}:
        raise ValueError("Each construction session needs one audited skill/material tag")
    versions = []
    for row in cases:
        session = row["session"]
        case = comparison_case(row, sources)
        tag = tags[session]
        skill, material = tag["skill"], tag["material"]
        # These English action options and their translation to letters were fixed before inference.
        # The researcher's reference action is deliberately not consulted.
        result = read_json(EXP / f"runs/text/{session}_reason.json")
        if result["version_reviewed"] != case["version"] or result["unresolved_citations"]:
            raise ValueError(f"Unverified upstream revision for {session}")
        decision = result["decision"]
        action = case["option_map"][decision["action"]]
        if action != result["selected_action"]:
            raise ValueError(f"Action mapping changed for {session}")
        original_material = tag.get("original_material", material)
        original = LessonVersion(case["version"], None, session, skill, original_material, "observed_lesson",
                                 row["learner_step"], "original", row["skill"],
                                 {"trajectory": case["source"], "design": case["design"]})
        if action == "probe":
            trigger = "choice_without_work"
            instruction = ("Before supplying the method, ask for one fresh, unaided step. "
                           "The step to elicit is: " + row["learner_step"])
        elif action == "retain":
            trigger, instruction = "independent_justification", ""
        else:
            # A named reason is required for targeted edits. Its material and reason tag are
            # narrower than a curriculum topic. A new learner's unsupported guess cannot trigger it.
            if not tag.get("observed_reason"):
                raise ValueError(f"Targeted edit requires a named observable reason for {session}")
            trigger, instruction = tag["observed_reason"], row[action]
        evidence = {"trajectory": case["source"], "reviewed_tutor_event": row["review_turn"],
                    "later_item_event": row["probe"], "later_learner_event": row["statement"],
                    "later_learner_text": case["later"]["reason"],
                    "model_decision_file": f"runs/text/{session}_reason.json",
                    "hypotheses": [decision["explanation_1"], decision["explanation_2"]],
                    "proposed_diagnostic": decision["diagnostic_material"],
                    "withdraw_if": decision["withdraw_if"]}
        versions += [original, LessonVersion(original.id.removesuffix("v1") + "v2", original.id,
                                              session, skill, material, trigger, row["learner_step"],
                                              action, instruction, evidence)]
    return SkillGraph(versions)
