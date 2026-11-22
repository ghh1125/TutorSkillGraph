# TutorSkillGraph research and implementation brief

[Project home](README.md) · [中文](RESEARCH_BRIEF.zh-CN.md)

**Can an AI tutor use students’ later independent work to learn when a combination of teaching moves is worth repeating?** The object that evolves is the tutor’s rule for choosing a move in a particular situation. The learner’s success on a new problem gives the tutor a reason to revisit that rule. The repository currently contains the research design. The mechanism below is a hypothesis and the first implementation milestone is open.

## Why a tutor can learn the wrong lesson

Two students can both get an answer right after a tutor says “compare these two cases.” One has already offered an explanation. The examples expose a prediction that follows from it, giving the student something specific to reconsider. The other has only stated an answer. The same examples may leave that student wondering what to look for. If the tutor counts both corrections as votes for “give more examples,” experience can reinforce a teaching move while obscuring the very condition that made it useful.

This leads to a concrete question about *designing instruction*: **what thinking has this learner already done, and what thinking will this material leave for the learner to do?** A study of 181 students gives a reason to ask. In that setting, delaying instruction alone did not improve conceptual understanding, and providing contrasting cases did not improve posttest results. The study did not test whether matching a contrast to a student's own explanation changes its value. That is our hypothesis to investigate. [Contrasting cases and the order of instruction](https://doi.org/10.1007/s11251-020-09504-7)

## One example that fixes the meaning of the graph

Suppose a learner says “one eighth is larger than one sixth because eight is larger than six.” A tutor can show two equal-sized strips, one divided into eight equal parts and the other into six, and ask the learner to predict which single piece is larger before looking. The material distinguishes two explanations which give opposite predictions. If another learner has only said “one eighth,” an initial “How did you decide?” can reveal whether those strips would address the same difficulty. This is an invented example of a design decision.

One role-labelled hyperedge would connect three things:

| Role | What the record means in this example |
| --- | --- |
| The learner’s expressed judgment | The quoted explanation establishes the learner’s prediction. An answer alone leaves the reason open. |
| What the chosen material tests | Both strips represent the same whole. The two explanations disagree on the comparison. Save what the tutor has already revealed in words or by pointing. |
| The thinking requested of the learner | Predict, compare and explain what would make the original judgment hold or fail. Keep the order when it changes what the learner must work out. |

This relation says **which idea this particular example is meant to test**. A list of actions such as “ask, show, explain” loses that correspondence. A conditional rule can represent it, as can a directed graph with a node for the combined state. An explicit hyperedge becomes interesting when moves and materials recur across many situations and their usefulness depends on their particular combination. Compare all representations with the same recorded information.

The intended reasoning belongs to the lesson design. **What the learner actually said or did next is a separate observation.** Link it to the source turn or event and record who introduced the key relationship. Link any later unassisted answer to the appropriate learner and task *within the same study*. At the moment of choosing the original move, only the history, candidate material and intended reasoning are available. Learning outcomes can inform a future rule update.

## What self-evolution would change

Start with the broad rule “after an error, offer a contrasting pair.” Suppose comparable attempts show that students who had expressed a judgment and received a pair that tested it later reasoned independently more often than under another plausible move. That pattern gives the tutor a reason to propose a narrower rule. For a future learner with an explicit judgment, choose a contrast that tests it. For someone who supplied only an answer, first elicit their reasoning. Direct explanation remains an option when it helps later independent work.

A **rule revision** should show the old rule, the revised condition, the original teaching episodes and independent outcomes behind the change, and one future situation in which the tutor would act differently. A performance gap between initially stronger and weaker students alone says little about which move helped. Compare alternatives within similar starting conditions, including prior help and task difficulty. If the records show only one move, they can suggest a condition to investigate. A later comparison of old and revised guidance with comparable learners is needed to establish a learning benefit.

## Where a new contributor should start

1. **Read the existing evidence and choose a tractable question.** The [project overview](README.md) explains the closest work and the five datasets. PEA contributes classroom event context. MM-TBA relates a planned student activity to what the teacher actually said. Scaffolded Error Correction is the starting point for studying routes to correction and related unassisted posttest items. GenAI Can Harm Learning and StudentBench offer external settings with different outcome measures. Carry the question between datasets and keep identities and outcomes within each study.
2. **Build one end-to-end decision before scaling up.** The first proposed artifact is a reader-inspectable record for one teaching decision. It should show what was known before the move, the three roles above, who actually contributed the key step, the available independent outcome and its source, and a proposed update or a reason to retain the rule. Start by checking whether the primary corpus contains an identifiable learner judgment, material and linked outcome for the chosen move. Contrasting examples illustrate the design. If that combination is rare there, document the coverage and use a supported combination such as asking the learner to justify an equation term.
3. **Make the change visible.** Present two new decision contexts, one with an expressed judgment and one with only an answer. Show which move the original and revised rules would select using only the information available then. On held-out learners, ask whether the recorded reasoning adds information beyond prior knowledge, task difficulty, correction and amount of help. Then compare the conditional rule, stateful graph and hypergraph. Historical prediction and a proposed change of action are different results from improving future learners’ outcomes.

The intended implementation uses a model API to locate evidence in text or annotations and ordinary CPU tools to store relationships, compare records and apply rule revisions. The project can start from published texts and event labels. The first milestone is ready for implementation. Its effect on students’ learning remains an open question.
