# EtlReverseEngineering Documentation

Reference docs for the RE workflow state machine. Each doc is self-contained.

| Looking for... | Go to |
|---|---|
| The 28 happy-path nodes, stages, model assignments, and what each does | [state-machine-overview.md](state-machine-overview.md) |
| Outcome routing, counter mechanics, FAIL self-retry, rewind, DEAD_LETTER | [transition-logic.md](transition-logic.md) |
| The 7-gate FBR gauntlet and fbr_return_pending | [fbr-gauntlet.md](fbr-gauntlet.md) |
| The 7-step triage sub-pipeline after proofmark failure | [triage-pipeline.md](triage-pipeline.md) |
| AgentNode, per-node model mapping, blueprint conventions, stdout JSON contract | [agent-integration.md](agent-integration.md) |
