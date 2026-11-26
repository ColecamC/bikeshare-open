---
name: seed-fault
description: Deliberately break the pipeline in one named way, record which check catches it (hook stderr, make test output), then restore the code. Use when asked to seed, plant, inject or simulate a fault, or to test whether the verification suite catches a specific bug.
allowed-tools: Read, Edit, Bash(make*), Bash(python -m pytest*), Bash(git diff*), Bash(git status*)
---

# Current state

!`git status --short`

Fault to seed: **$ARGUMENTS**

A seeded fault is an experiment on the verification suite, not on the model.
The question is: which check catches this bug, and how fast? A fault that
nothing catches is the most useful result, so report it plainly instead of
making it go red some other way.

Work in this order. Stop at the first step that does not go as described.

1. **Start clean.** If `git status --short` above lists anything under
   `src/` or `tests/`, stop and say so. A fault seeded on top of other
   changes cannot be attributed.

2. **State the prediction in one sentence before editing:** which test
   should fail and why, or "nothing should catch this" and why.

3. **Make exactly one edit** with the Edit tool, under `src/`, so the
   PostToolUse hook runs. Do not touch `data/raw/`, `tests/`, or
   `.claude/`. Then stop and do not fix anything the hook reports: the
   point is to see the failure, not to clear it.

4. **Record the evidence**, exactly as printed, not paraphrased:
   - the diff: `git diff -- <file>`
   - the hook's message, or "the hook did not fire" (it only runs
     `tests/test_leakage.py` after edits to `src/*.py`)
   - `make test`: the full failure and the summary line.

5. **Compare with the prediction.** If the suite stays green, the fault
   exposes a gap: name the guard that no test exercises, and propose the
   test that would. Do not write it here; that is a separate change, made
   test-first.

6. **Restore** by reversing your edit with the Edit tool. Confirm that
   `git diff -- <file>` is empty and that `make test` passes. Never use
   git to commit, reset or check out: the user does all git operations,
   and committing the broken state would name the fault in the next
   session's context.

7. **Report** in this shape, ready to paste into `docs/SEEDED_FAULTS.md`:
   `## Fault: <one line>`, then **The change** (diff), **Hook stderr**,
   **`make test` output**, **Caught by** (test name, or "nothing"), and
   **Gap** (if any).

Faults that write to `data/raw/` cannot go through this skill: the deny
rules block the Edit tool there, and the file's sha256 is checked by
`make data` and `tests/test_contract.py::test_raw_file_is_unchanged`. See
fault 4 in `docs/SEEDED_FAULTS.md` for how that one was done and restored.
