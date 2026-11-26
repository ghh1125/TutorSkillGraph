# TutorSkillGraph

English · [中文](README.zh-CN.md)

**A student gets the right answer after a hint. Should the tutor give the same hint to the next student?** TutorSkillGraph uses classroom records and students' later independent work to improve what a tutor asks next. A hypergraph preserves the conditions that held together in one lesson. A versioned *teaching skill* records a move the tutor can reuse and the evidence that would justify changing it.

[Paired replay results](#paired-replay-results) · [Method and code walkthrough (Chinese)](METHOD.zh-CN.md) · [Data and reproduction (Chinese)](data/README.md)

## Two students got the same answer. Why ask them different questions?

In two StudentBench GRE math sessions, students were asked to compare x³ and x² for x > 0. Both eventually submitted the correct choice, D, meaning that the relationship can change with x. The turns before those submissions tell different stories.

| Session | What the classroom record shows | What the tutor could do next |
| --- | --- | --- |
| 0402 | The student said x³ must be greater because its exponent is larger. The tutor worked through x=2, suggested trying 1 and a fraction, and later explained the outcomes. The student then submitted D. | Offer a positive number below 1. Let the learner calculate both powers and say when their original claim holds. |
| 0608 | Before the tutor responded to this problem, the student pointed out that the powers are equal at x=1 and that x³ is greater for x>1. Those two outcomes already establish D. | Acknowledge that the student's argument settles the comparison and move on. |

The first two columns come from classroom records. The last is our teaching judgment. At x=2, a student who believes “the larger exponent always wins” and one who understands the role of the base will both get 8 > 4. Tutors also adapt their hints to the difficulty a student shows. **To tell what a learner has mastered, we need to know whether the example could distinguish the two ideas and who first supplied the decisive reasoning.** [Session 0402](data/raw/studentbench-reasons/task_id_0402.csv) · [Session 0608](data/raw/studentbench-reasons/task_id_0608.csv)

Evidence of independent work arrives later. In session 0608, the learner also submitted a correct answer on a subsequent problem of the same kind before receiving any feedback on that problem. That attempt can inform a revision for future lessons. When choosing a move for the current learner, the system uses their pre-lesson profile and plan and reads the dialogue only up to the current turn. [Classroom episodes and their later evidence](experiments/grounded_tutor/memory.json)

## What does a hypergraph add to an ordinary graph?

An edge in an ordinary graph connects two nodes. It is a natural way to record which student attempted an exercise or which exercise tests powers. A query for “students who correctly answered the powers question” finds both 0402 and 0608. Adding a link that says “a fraction was used in class” could still give the learner in 0402 credit for a calculation the tutor demonstrated. Deciding whom to ask for a counterexample requires knowing what role each fact played in the same teaching decision.

A *hyperedge* can connect several nodes at once. In our classroom graph, **one hyperedge represents one teaching decision point**. Its nodes have five roles. They identify the exercise family, mathematical goal, observed learner state, help already supplied, and candidate teaching move. Here is the edge for the exchange in 0608.

| Exercise family and goal | Learner state and prior help | Candidate teaching move |
| --- | --- | --- |
| Compare powers with a positive base and decide whether the ordering can change | The tutor has yet to reply to this exercise. The learner has already given two distinct outcomes. | Acknowledge that these outcomes establish the argument |

A query matches conditions on the same edge. The edge also carries the positions of the problem, the learner's message, and the tutor's actual reply, so a reader can inspect the exchange behind the match. [Classroom graph implementation](src/tutorskillgraph/grounded_skill.py) · [Graph diagram and worked examples (Chinese)](METHOD.zh-CN.md)

An ordinary graph can preserve the same information by adding a node for each teaching event and labelling its links by role. We use a hypergraph because **one teaching decision is directly retrievable and citable as a unit**. Two episodes can share a topic or teaching move while keeping their own materials, the turns showing who did the reasoning, and the later evidence for a revision. A condition table with the same fields retrieved the same lesson edits in our 32-session replay. [Per-session retrieval records](experiments/grounded_tutor/runs/design_lock.json)

## Why represent a teaching move as a skill?

“Compare powers” names something the student is learning. A **teaching skill** specifies an action the tutor can reuse, such as asking a learner to choose a legal value that changes the ordering found on the first try. The skill states when to use it, which material to choose, and which step the learner should perform. A proposed revision also records the evidence that would let the tutor retire the extra prompt.

- **Revise a specific part of a lesson.** The earlier plan in session 0402 called for testing powers with admissible values. Trying 2 and 3 would twice favor the larger exponent. The learner's later explanation identified a reason to change the examples. The candidate version keeps the comparison task and calls for positive bases on either side of 1. Using 2 gives 8 > 4. Using 1/2 gives 1/8 < 1/4. If the learner can explain on a fresh problem, unaided, why (1/2)³ < (1/2)², the tutor can drop this extra prompt. The new version points back to its parent and to the learner's words. [0402 revision and withdrawal condition](experiments/reason_ablation/runs/text/task_id_0402_reason.json) · [Version records](experiments/reason_ablation/native_runs/skill_graph.json)
- **Reuse the move on different material.** In a separate held-out session, 0664, the learner chose the answer that x−y was positive. The constraints (x−4)(x+1)=0 and x+y=2 permit both x=4, y=−2 and x=−1, y=3. The revised plan supplied the second valid pair and left the learner to compare −1−3 with zero. What carries over is the instruction to test the learner's claim. The values come from the new problem's constraints. [0664 lesson plan and source evidence](experiments/evidence_revision/runs/design_lock.json) · [Replies under both plans](experiments/evidence_revision/runs/comparisons.json)
- **Update the lesson with a fixed model.** A revision adds a record to the skill library. The CPU retrieves a matching move and checks the proposed values. The system adds the instruction to the current lesson's `why_it_matters` field, and the published StudentBench tutor strategy generates the reply. The update is lightweight because a change to one teaching move can reach the next lesson with the small model's weights held fixed. [Skill library](src/tutorskillgraph/skill_graph.py) · [Evidence-based selection](src/tutorskillgraph/evidence_revision.py) · [Final inference](src/tutorskillgraph/grounded_trials.py)

## Paired replay results

Each session contributes one point at which a real student had spoken or submitted an answer. Both arms use the same learner profile, visible dialogue, `gpt-6-luna`, and published StudentBench strategy, `gre.quant.tutor.lean.v3`. We specified each teaching objective before generation and scored the replies with their sources hidden. The outcome is whether the tutor's **next reply** addresses the learner correctly and leaves them a meaningful step, or acknowledges a sufficient argument and moves on.

| Held-out sessions | StudentBench original plan met the objective | TutorSkillGraph plan met the objective |
| --- | ---: | ---: |
| 32 sessions with moves and materials selected from the classroom state | 17/32 (53.1%) | 23/32 (71.9%) |
| 24 additional sessions with material selection revised using earlier learners' independent attempts | 11/24 (45.8%) | 19/24 (79.2%) |

The historical classrooms contained 62 pairs of submissions in which the learner first correctly chose “the relationship can vary.” On 15 of the subsequent, independently attempted problems, the learner picked a fixed ordering. The new rule uses these observations to select a value that tests a particular ordering on the *current* exercise. In the six sessions in the second batch where this prompt applied, the original and TutorSkillGraph plans met the objective in three and six cases, respectively. [32-session report (Chinese)](experiments/grounded_tutor/REPORT.zh-CN.md) · [24-session report (Chinese)](experiments/evidence_revision/REPORT.zh-CN.md)

An earlier pilot built candidate skills from 12 classrooms. In its two held-out replays, the original and revised plans met the teaching objective in zero and one case, respectively. We also reproduced the fence dataset authors' regression baseline. Among 50 learners who ultimately solved the one-gate problem, adding who first mentioned subtracting the gate width did not improve prediction of the combined independent posttest score. For learner p019, the release records the corrected equation after a hint and a combined score over three transfer items. The learner's answer and reasoning on the two-gate item remain unknown, so the proposed lesson edit is still open to testing. [StudentBench pilot](experiments/reason_ablation/REPORT.zh-CN.md) · [Fence and transfer analyses](experiments/lesson_revision_pilot/REPORT.zh-CN.md) · [p019 record and competing explanations](cases/p019.zh-CN.md)

## Inspect the implementation and reproduce the results

To rebuild the p019 case with the Python standard library, run these commands from the repository root with Python 3.11 or later. The data guide lists the dependencies for StudentBench and the commands to recalculate its results from the saved replies. [Structured p019 record](cases/p019.json) · [Data and reproduction](data/README.md) · [Full research brief in English](RESEARCH_BRIEF.md)

```sh
python scripts/fetch_sec.py
python scripts/build_p019.py
python -m unittest discover -s tests -v
```

The case implementation links source turns, evaluates the proposed change, and builds the human-readable report from the same record. [Evidence lookup](src/tutorskillgraph/evidence.py) · [Fence revision logic](src/tutorskillgraph/revision.py) · [Case builder](src/tutorskillgraph/build.py) · [Report generator](src/tutorskillgraph/report.py)

## Research context and datasets

<details>
<summary>Earlier work and the questions it leaves open</summary>

| Earlier work | Its contribution and the question it leaves us |
| --- | --- |
| [Data-driven redesign of intelligent tutors](https://arxiv.org/abs/2603.29094) and [instruction with contrasting cases](https://aaalab.stanford.edu/assets/papers/2011/Practicing_versus_inventing.pdf) | Redesigning practice from learner data and selecting contrasts to support transfer both have precedents. We ask whether later student reasoning can reveal why two explanations worked on the original example and guide the tutor to a specific edit. |
| [Turning Errors into Successes, §4.6](https://arxiv.org/pdf/2611.20061) | In the Socratic group, correcting more errors was associated with better performance on practice-aligned transfer questions after accounting for initial successes. Our interest is the variation **among successful corrections**. |
| [Pedagogical tutorial tactics](https://people.cs.pitt.edu/~litman/5-Chi.pdf) and [research on self-explaining feedback](https://doi.org/10.1016/j.cedpsych.2024.102326) | Tutors have already learned action policies from student outcomes. Experiments also show that the benefit of explaining one's errors depends on the feedback students receive. The open issue here is which part of a particular success deserves credit when updating a reusable rule. |
| [REAT](https://arxiv.org/html/2609.29804v1) and [Eduardo](https://arxiv.org/abs/2610.06446) | REAT distils and retrieves tutoring experience and updates its utility from subsequent turn evaluation. Eduardo uses a simulated student's near-transfer test with tutor turns masked. We ask whether an observed human learner's route through a correction can identify **which experience** to keep or narrow. |
| [StratL](https://aclanthology.org/2025.findings-acl.1348/) and two [HyperSkill](https://arxiv.org/abs/2608.16114) [frameworks](https://arxiv.org/abs/2611.15178) | Prescribed multi-turn teaching graphs, evolving skill hypergraphs and training-free skill composition all have precedents. The proposed contribution is a way to decide when a tutoring success warrants changing an instructional rule. The graph earns its place only if it improves that decision. |

</details>

<details>
<summary>What the five datasets in the research plan can tell us</summary>

**1. PEA classroom videos — discover what a transcript can miss.** A student may be the first to *say* which side of a diagram is missing even though the teacher has just pointed it out. A text-only tutor could give the student's answer, or its own last question, too much credit. PEA aligns five lesson stages with 27 types of verbal and non-verbal events in 100 mathematics and information-technology classroom videos. Its public event timelines let us locate questions that overlap with gestures and compare when they occur. With authorized footage, a reader could inspect what the gesture indicated. This gives the skill graph a concrete design choice: record evidence that was available to the learner through speech **and** demonstration. An event label alone cannot tell us which idea a gesture conveyed or whether a particular student learned it. The annotations and taxonomy are public; the authors describe controlled access for the raw videos. [PEA paper](https://doi.org/10.1145/3767308.3838632) · [Dataset](https://github.com/mark1001-ljj/dataset_event) · [Video access](https://github.com/mark1001-ljj/dataset_event/blob/main/docs/VIDEO_ACCESS.md)

**2. MM-TBA — compare a planned teaching move with the words used in class.** The instructional-design subset pairs trainee teachers' original lesson plans with annotated teaching intervals and the corresponding transcript passages. That lets us ask a question a gesture label alone leaves open: if the plan asks students to discover a relationship, did the teacher's preceding words already supply it? Record the planned student activity and the information actually supplied as separate fields on a candidate skill. Start with the linked texts and annotations. The action-detection subset releases visual features and second-by-second labels for six actions, including pointing and writing; raw classroom footage is not distributed. The model-generated lecture reports assess instruction. To find out what learners can subsequently do alone, carry the resulting hypothesis into the outcome studies below. [Paper and data description](https://www.nature.com/articles/s41597-025-05426-6) · [Figshare release](https://doi.org/10.6084/m9.figshare.28942487)

**3. Scaffolded Error Correction — distinguish routes to the same correct answer.** This is the starting point for the core question. The study assigned 400 adults to four feedback conditions, including 99 in the Socratic group. The public files contain participant outcomes and tutoring logs. All participants took a five-item posttest without feedback, including three harder variants of the practice problems. The protocol allowed the tutor to supply the equation after six unsuccessful tutor replies. This creates a reason to check who first supplied the critical relationship and what the student subsequently did with it. Compare routes to correction against the corresponding practice-aligned outcome. [Data and codebook](https://github.com/the-oak-lab/scaffolded-error-correction) · [Study protocol](https://arxiv.org/pdf/2611.20061)

**4. GenAI Can Harm Learning — check the distinction in a high-school classroom.** The study released timestamped student–GPT conversations, assisted practice scores, unassisted exam scores and the authors' mapping from practice problems to related exam problems. The ordinary GPT and tutor-guided conditions give us two settings with different amounts and forms of help. Ask whether a pattern found in the adult equation study still distinguishes independent performance in school mathematics. The dialogue table calls its student identifier `username` and the score table uses `Student_ID`. A student-level claim requires verifying that mapping as well as matching session and problem. Until then, the published condition-level comparisons support a narrower comparison of practice and exam performance. [Data dictionary and problem mapping](https://github.com/obastani/GenAICanHarmLearning) · [PNAS paper](https://doi.org/10.1073/pnas.2422633122)

**5. StudentBench — test whether the rule travels across tutors and subjects.** This GRE study covers 2,383 participants and 2,469 sessions, spanning quantitative and verbal reasoning. Its public release includes tutoring conversations, practice attempts, and responses to 27-item pretests and posttests. The AI-tutored sessions let us ask whether a rule developed on equations also carries information about a learner's later performance with a different tutor or in a verbal task. Use pretest performance and section as context, and link conversations and assessments within the same session. The released `student_id` identifies a session; the authors do not provide a person-level key linking the two sections. An overall session gain alone cannot identify which individual utterance helped. [Dataset and identifier guide](https://huggingface.co/datasets/handshake-ai-research/studentbench) · [Study](https://arxiv.org/abs/2609.28470)

Use PEA to identify a teaching move within a classroom sequence and MM-TBA to separate its planned purpose from the clues a teacher actually gave. Carry the **teaching hypothesis** into Scaffolded Error Correction, define it against independent work there, then keep that definition fixed in the two external studies. Each source contributes evidence at its own level, from classroom events and plan–transcript passages to practice-aligned transfer, unassisted exam scores and pretest-adjusted GRE performance. Compare the findings across studies without linking individuals across datasets.

</details>

<details>
<summary>Testing whether a revised lesson improves independent learning</summary>

The first comparison is deliberately small. Use the same pretest and task information throughout. Ask how well independent performance can be anticipated from **correction alone**, then from **correction plus amount of help**, then from **who supplied the key step and how the student used it**. Compare on students whose conversations were excluded when forming the rules. If the last description adds information, compare a plain conditional rule or stateful directed graph with the role-labelled hypergraph using identical evidence. A simple rule that performs equally well is a good outcome: it identifies the instructional distinction without adding machinery.

An API-accessed language model could locate the relevant turns. Each judgment should point back to an utterance and allow an ambiguous reading; a human reader can check a sample. The graph, counts and comparisons can run on an ordinary CPU. No model fine-tuning or classroom-video processing is required by this design.

The primary error-correction study can test whether these histories distinguish outcomes. Its four feedback conditions were randomized, but individual questions within a Socratic conversation were adaptive. A tutor may give more help precisely because a student is struggling. Showing that a revised rule **improves** future learning would require a separate comparison in which comparable learners receive the original or revised guidance. That distinction defines how far the first study can take the idea.

</details>
