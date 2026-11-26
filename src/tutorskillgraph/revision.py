"""Predictions and pre-specified revision decisions for the single-gate lesson."""

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class GateTask:
    name: str
    widths: tuple[int, ...]
    fence: int
    provenance: str

    def equation(self, deduction: int) -> str:
        return f"2x + 2y − {deduction} = {self.fence}"

    def predictions(self) -> dict:
        # B leaves open which gate the learner would choose when widths differ.
        return {
            "task": self.name, "gate_widths_ft": self.widths, "fence_ft": self.fence,
            "task_origin": self.provenance, "all_openings": self.equation(sum(self.widths)),
            "one_opening_only": [self.equation(w) for w in dict.fromkeys(self.widths)],
        }


ORIGINAL = GateTask("原练习", (10,), 500, "公开练习，第 7 轮有真实回答")
PROBE = GateTask("等宽双门诊断题", (10, 10), 500, "本项目设计，未对 p019 施测")
PUBLIC_TEST = GateTask("Farm Gates", (12, 8), 500, "公开后测题，p019 的逐题作答未知")


class Reason(Enum):
    ACCOUNTS_FOR_BOTH = "理由逐一解释两处开口都无需围栏"
    CLAIMS_ONLY_ONE = "理由明确主张即使有两处开口也只该扣一处"
    UNINFORMATIVE = "未说明理由、只复述数字或理由不清"


@dataclass(frozen=True)
class ProbeResponse:
    """Human-coded response to the specified two-10-ft-gates probe.

    Supply deduction_ft = d only for an equation algebraically equivalent to
    2x + 2y - d = 500. Use None for a different perimeter, an unreadable
    response, or any answer that cannot be scored in that form.
    The booleans refer to conditions at the time of this particular response.
    """
    deduction_ft: int | None
    reason: Reason
    unaided: bool
    first_exposure: bool
    before_revision: bool


class Decision(Enum):
    PENDING = "待取证"
    WITHDRAW = "撤回对此学生补教多门计数的建议"
    TRY = "可针对单门规则试用对照"
    CLARIFY = "追问理由或复核列式"


def assess_probe(response: ProbeResponse | None) -> Decision:
    """Judge the proposed addition for one learner; no cohort efficacy inference."""
    if response is None or not (response.unaided and response.first_exposure and response.before_revision):
        return Decision.PENDING
    if response.reason is Reason.ACCOUNTS_FOR_BOTH and response.deduction_ft == sum(PROBE.widths):
        return Decision.WITHDRAW
    if response.reason is Reason.CLAIMS_ONLY_ONE and response.deduction_ft in PROBE.widths:
        return Decision.TRY
    return Decision.CLARIFY


def proposed_revision() -> dict:
    return {
        "purpose": "检验单门纠错结束时，学生能否自行根据所有开口决定扣去的长度。若相似学生反复主张有多个开口也只扣一处，则试改结尾。",
        "interpretations": {
            "all_openings": "A 按实际缺口计数。每个无需围栏的开口都从完整周长中扣去一次。",
            "one_opening_only": "B 把单门做法推广成只扣一处门宽，即使有多个开口也只选一处。",
        },
        "relationship_to_observation": "A、B 是我们为第 7 轮正确式子提出的两种可能理解。第 5 轮学生亲口说过删去整条边，那是更早的判断。提示后照着写、偶然漏读一个门、算术失误也能影响回答。",
        "predictions": [task.predictions() for task in (ORIGINAL, PROBE, PUBLIC_TEST)],
        "probe_prompt": "一个矩形院子的边长为 x、y 英尺。一条 x 边和一条 y 边各有一个 10 英尺宽的门洞，门洞处无需围栏。可用围栏共 500 英尺。请列方程，并解释你为什么这样列。",
        "interpret_probe": "研究者在给反馈前保存学生的首答、完整理由和已获得的提示。A 预期学生解释两个门都不用围，因此共扣 20。B 预期学生说这道题只需扣一个门，因此扣 10。等价移项照样认可，单看最后的数值无法识别理由。",
        "individual_criteria": {
            "withdraw": "修订前，学生首次独立做等宽双门题，写出等价于扣 20 的方程，并自行说明两处门洞各省 10。撤回给该学生增设多门对照的建议。",
            "try": "相同条件下写出扣 10，并明确解释两个门也只应扣一处。此回答支持为该学生试用针对性对照。诊断题此时已见过，后续测验须换题。",
            "clarify": "只写减 10 或减 20、理由含糊，或式子与理由矛盾，均保留未决。若学生逐一写了两个门却算错总数，先让他重算，以区分算术和计数问题。",
            "pending": "缺少独立首答、只看到合计分，或题目已讲过、导师已提示扣两个门时，保持待取证。",
        },
        "edit": {
            "location": "原课第 7 轮学生写对之后，第 8 轮确认答案之处。",
            "v0": "导师确认单门方程，复述从矩形周长中扣去十英尺门洞的理由，结束本题。",
            "v1": "面向下一批起点相近的学生，在同一位置确认单门式子，接着把题面改为两条边各有一个同宽门洞。让学生自行列式并解释，再按其理由反馈。",
            "control": "要检验改课收益，两组在相同时间内各完成一次额外列式并解释。对照组换一组数字做单门题，修订组做双门对照。两组使用相同的回复机会和反馈时间。",
            "transfer": "另留一题，两组在教学后均首次独立作答。例如矩形展板外框实际装饰条长 360 厘米，三个分开的开口宽 3、5、7 厘米。边长为 x、y 厘米时应得 2x+2y−15=360，理由需逐一对应三个开口。等宽双门题一旦用于教学或诊断，就退出该学生的效果测验。",
            "cohort_withdrawal": "在起点可比、教学时间和练习次数匹配的随机比较中，预先约定以新题上方程与理由均正确的学生比例作为指标。若修订组减对照组之差的预设置信区间上界 ≤ 0，撤回向这一人群推广该改法的建议。区间仍包含有意义的改善时保留未决。个人一次回答只影响对该学生的补教决定。",
        },
        "observed_probe_response": None,
        "current_decision": assess_probe(None).value,
    }
