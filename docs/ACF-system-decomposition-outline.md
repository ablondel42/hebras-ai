# System Decomposition Outline

This outline breaks the current product idea into chart-ready parts so the system can be remembered, refined, and later turned into diagrams.

## 1. Main poles

| Pole | Purpose | Main question it answers | Key artifacts |
|---|---|---|---|
| Human control | Keep the human as final authority | Who decides and approves? | approvals, overrides, decision records |
| Structured artifacts | Turn ideas into inspectable building blocks | What is the project made of? | artifact graph, schemas, contracts, tree nodes |
| LLM assistance | Use models as scoped workhorses | What can the model propose or draft? | prompts, candidate artifacts, evidence packets |
| Review and feedback | Improve quality and trust over time | How do we detect drift and correct it? | gate checks, audit logs, review notes, feedback loops |

## 2. Core actors

| Actor | Role in system | Authority | Main outputs |
|---|---|---|---|
| Human operator | Sets goals, reviews, approves, rejects | Final authority | approvals, edits, priorities, constraints |
| Orchestrator | Routes work, controls stage transitions, packages handoffs | Procedural authority only | task packets, handoff packets, state transitions |
| Floor agent | Specialized worker for one phase/floor | Limited to assigned scope | candidate artifacts for that floor |
| Builder agent | Generates implementation candidates in strict scope | Limited by approved artifacts | class proposals, property proposals, method proposals |
| Reviewer / gatekeeper | Validates outputs against schema and definition of done | Can block promotion | review verdicts, rejection reasons, change requests |
| Audit observer | Records what happened and why | No execution authority | logs, traces, provenance, decision history |
| Compiler / validator | Converts approved source artifacts into graph state | Structural authority only | validated graph, errors, warnings |
| Real workspace | Execution target after approval | No independent authority | actual files, commits, promoted artifacts |

## 3. Main flows

### Flow A — Idea to graph
1. Human writes or imports raw idea/docs.
2. Level-0 decomposition converts input into proposed structured artifacts.
3. Artifacts are classified by type and validated.
4. Human reviews proposed graph units.
5. Approved artifacts enter official graph.

### Flow B — Graph to preview build
1. Orchestrator selects a narrow execution slice from approved graph.
2. Relevant floor agent receives packetized context.
3. Agent generates candidate artifacts in preview/sandbox.
4. Validator checks schema, rules, and evidence.
5. Human reviews branch or node output.

### Flow C — Preview to workspace
1. Human approves a candidate artifact or branch.
2. System promotes it through a non-token apply step.
3. Real workspace updates the actual project files.
4. Audit layer records what changed, why, and from which preview.

### Flow D — Feedback loop
1. Output is reviewed or used.
2. Problems, gaps, or drift are detected.
3. Feedback is attached to artifact, prompt, rule, or agent packet.
4. Docs, schemas, or instructions are improved.
5. Future runs use the better contract.

## 4. Agent families

| Agent family | Scope | Should do | Must not do |
|---|---|---|---|
| Floor 0 / decomposition agent | Convert large docs into proposed artifacts | extract, classify, structure, link | directly code or invent approved state |
| Planning / exploratory agent | Build coherent artifact chains | consolidate, question, organize dependencies | skip evidence or collapse all phases together |
| Floor agents | Work within one project phase | ask phase-specific questions, produce phase outputs | cross phase without handoff |
| Builder agents | Generate implementation candidates by scope | propose classes, then properties, then methods | jump straight to uncontrolled full-project code |
| Review agents | Check compliance and quality | validate schema, DoD, security, relationships | silently approve weak outputs |
| Documentation agents | Maintain human-readable system knowledge | summarize, explain, update docs | become source of truth without review |
| Observer agents | Track behavior and provenance | log, trace, compare runs | mutate state directly |

## 5. Main state containers

| Container | What lives there | Why it exists |
|---|---|---|
| Raw input space | notes, briefs, docs, imported sources | capture intent before structure |
| Preview / sandbox | temporary candidate artifacts and proposed diffs | safe place for generation |
| Gatekeep layer | schemas, rules, checks, approval states | stop drift and enforce quality |
| Official graph / project memory | approved nodes, edges, metadata, decision history | stable source of truth |
| Real workspace | actual code and files | execution target after approval |
| Audit store | traces, logs, rationale, promotion history | replay, trust, debugging |

## 6. Relations to chart

### Pole-to-pole relation
- Human control governs every other pole.
- Structured artifacts are the backbone.
- LLM assistance operates inside artifact and policy boundaries.
- Review and feedback close the loop and improve future runs.

### Actor-to-flow relation
- Human starts, reviews, and approves.
- Orchestrator routes and sequences.
- Agents generate within packet scope.
- Validator and reviewer block weak work.
- Compiler promotes approved structure into official state.
- Workspace only changes after explicit approval.
- Audit observer records everything.

## 7. Suggested charts to make

1. **Pole map** — 4 poles with arrows between them.
2. **Actor map** — human, orchestrator, floor agents, builder, reviewer, compiler, audit, workspace.
3. **Main lifecycle** — raw idea -> decomposition -> preview -> gatekeep -> graph -> apply -> workspace.
4. **Agent ladder** — floor 0, planning, floor agents, builder agents, review agents, observer.
5. **State diagram** — raw input, sandbox, gatekeep, graph, workspace, audit.
6. **Authority map** — who can propose, who can validate, who can approve, who can apply.
7. **Feedback loop** — output -> review -> correction -> docs/schemas -> improved future run.

## 8. The shortest system sentence

A human-controlled, graph-driven builder system where LLMs generate scoped candidate artifacts, validators and reviewers gate them, and only approved outputs are promoted into the real workspace.
