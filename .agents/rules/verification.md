---
description: Strict verification standard — real input/output testing required; mocks are never a Definition of Done.
globs: ["**/*"]
always_on: true
---

# Real Verification Standard & Definition of Done

1. **Mocks are NEVER the "Definition of Done"**:
   - Mocking in/out components is only an auxiliary unit-level smoke check, never proof of functional completion.
   - Work must NEVER be presented as completed based solely on mocked tests.

2. **Real Input / Output Verification is Mandatory**:
   - Only real in/out tests (executing against live binaries, real subprocesses, live endpoints, and verifying actual on-disk logs and responses) qualify as success.

3. **Verification is Primordial**:
   - Always perform live verification in the real environment before concluding any task.
