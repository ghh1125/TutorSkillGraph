# TutorSkillGraph

English · [中文](README.zh-CN.md)

**When a student corrects an answer, what should an AI tutor learn from that success?** TutorSkillGraph is a research proposal about how a tutor revises the teaching strategies it reuses with future learners. Its target is a student who can take the key reasoning step on a new problem after the help is gone.

## The problem with learning from a successful lesson

Imagine two students who have left a term out of a fence-length equation. The first explains what each term counts. The tutor asks which sides of the fence that explanation covers. The student notices the missing side and fixes the equation. In a second conversation, the tutor names the missing side and asks the same question. The second student also fixes the equation. This is an illustrative pair, not a pair of observations from the dataset.

Both tutors may have helped. What differs is the evidence each conversation provides about the value of the question. In the first, the student supplied the missing relationship after the prompt. In the second, the tutor had already supplied it. A tutor that gives its question credit every time the answer turns correct can gradually learn the wrong lesson about when to ask it. Simply penalizing explicit help can make the opposite mistake: a clear explanation may be exactly what allows a student to apply the idea independently later.

**Our question is whether the *route to a correction* tells us which teaching experience to reuse.** Among students who ultimately correct a similar error and start with comparable knowledge, does tracing where the key relationship first appeared, and what the student subsequently did with it, help anticipate independent performance on a related problem? If it does, that evidence could change what the tutor does the next time it encounters that difficulty.

## What earlier work has already established

| Earlier work | Its contribution and the question it leaves us |
| --- | --- |
| [Turning Errors into Successes, §4.6](https://arxiv.org/pdf/2611.20061) | In the Socratic group, correcting more errors was associated with better performance on practice-aligned transfer questions after accounting for initial successes. Our interest is the variation **among successful corrections**. |
| [Pedagogical tutorial tactics](https://people.cs.pitt.edu/~litman/5-Chi.pdf) and [research on self-explaining feedback](https://doi.org/10.1016/j.cedpsych.2024.102326) | Tutors have already learned action policies from student outcomes. Experiments also show that the benefit of explaining one's errors depends on the feedback students receive. The open issue here is which part of a particular success deserves credit when updating a reusable rule. |
| [REAT](https://arxiv.org/html/2609.29804v1) and [Eduardo](https://arxiv.org/abs/2610.06446) | REAT distils and retrieves tutoring experience and updates its utility from subsequent turn evaluation. Eduardo uses a simulated student's near-transfer test with tutor turns masked. We ask whether an observed human learner's route through a correction can identify **which experience** to keep or narrow. |
| [StratL](https://aclanthology.org/2025.findings-acl.1348/) and two [HyperSkill](https://arxiv.org/abs/2608.16114) [frameworks](https://arxiv.org/abs/2611.15178) | Prescribed multi-turn teaching graphs, evolving skill hypergraphs and training-free skill composition all have precedents. The proposed contribution is a way to decide when a tutoring success warrants changing an instructional rule. The graph earns its place only if it improves that decision. |

## The idea: revise the conditions under which a teaching move is reused

A teaching skill is a reusable move, such as asking a student to justify a term. The graph would record a relationship between **what the student has already shown, what the tutor does, and what reasoning the student subsequently contributes**. A hyperedge can keep these roles together. This matters when the same question serves different purposes depending on what the student has already worked out and what earlier hints have revealed.

| Point in the interaction | Evidence the tutor could use |
| --- | --- |
| Before choosing a move | The task goal, the student's visible attempt or explanation, and information already supplied by the tutor. An equation alone may leave the student's reasoning ambiguous. |
| After the response | The tutor's actual move and the student's next contribution. Did the student introduce the relevant relationship, apply one that had been explained, or simply repeat it? The dialogue may also leave this unclear. |
| After independent work | The same learner's answer on a related, unassisted item. This becomes evidence for revising the rule for future learners. It is unavailable when choosing the original move. |

Suppose the current rule is “ask for justification after an incorrect equation.” If independent performance differs consistently between comparable cases where students have already articulated a model and cases where they have only entered an answer, the tutor could split that rule. It might ask the first group to test its reasoning and ask the second to explain what its terms represent first. If a supplied explanation also transfers well, the library should preserve that use of direct help. These are possible revisions; their value is an empirical question.

## Two datasets with different jobs

**Primary: Scaffolded Error Correction.** The study randomly assigned 400 adults to four feedback conditions. The Socratic condition had 99 participants. The public release includes participant-level outcomes, interaction logs and a codebook. Five immediate posttest items were answered without feedback, including three harder variants aligned with the practice problems. The protocol allowed the tutor to give the correct equation after six unsuccessful tutor replies. This makes it particularly important to inspect how a correct answer arose. The dialogue records what people said or typed; private understanding has to be inferred from subsequent performance. [Data and codebook](https://github.com/the-oak-lab/scaffolded-error-correction) · [Study protocol, §§3.4–3.6](https://arxiv.org/pdf/2611.20061)

**Supporting: PEA classroom event annotations.** PEA aligns five lesson stages with 27 types of verbal and non-verbal events across 100 mathematics and information-technology classroom videos. Its public release includes event timings and a taxonomy with typical predecessors, successors and expected instructional functions. These can suggest teaching moves and contexts worth looking for. The expected function is a class definition; the released annotations do not measure individual learning gains. PEA and the tutoring study describe different participants. Only the teaching hypotheses travel between them. [PEA paper](https://doi.org/10.1145/3767308.3838632) · [Public annotations and access details](https://github.com/mark1001-ljj/dataset_event)

## What would make the idea worthwhile?

The first comparison is deliberately small. Use the same pretest and task information throughout. Ask how well independent performance can be anticipated from **correction alone**, then from **correction plus amount of help**, then from **who supplied the key step and how the student used it**. Compare on students whose conversations were excluded when forming the rules. If the last description adds information, compare a plain conditional rule or stateful directed graph with the role-labelled hypergraph using identical evidence. A simple rule that performs equally well is a good outcome: it identifies the instructional distinction without adding machinery.

An API-accessed language model could locate the relevant turns. Each judgment should point back to an utterance and allow an ambiguous reading; a human reader can check a sample. The graph, counts and comparisons can run on an ordinary CPU. No model fine-tuning or classroom-video processing is required by this design.

The public study can test whether these histories distinguish outcomes. Its four feedback conditions were randomized, but individual questions within a Socratic conversation were adaptive. A tutor may give more help precisely because a student is struggling. Showing that a revised rule **improves** future learning would require a separate comparison in which comparable learners receive the original or revised guidance. That distinction defines how far the first study can take the idea.
