# Development process

## The rule

No code without a spec. No implementation without tests. No feature without discussion.

## The workflow: Spec-Driven Development + TDD

### 1. Spec first

Every feature starts as a written description in `docs/`. What does the operator experience? What are the inputs, outputs, constraints? What does "done" look like?

The spec is discussed and agreed before any code is written. Disagreements are resolved in the spec, not in a pull request.

### 2. Break into features

A spec describes an experience. Features are the buildable pieces of that experience. Each feature should be small enough to implement and test in one session.

Features are listed in the spec or in a separate feature breakdown document. Each feature has:
- A clear description (one sentence)
- Acceptance criteria (when is it done?)
- Dependencies (what must exist before this?)

### 3. Tests first, then implementation

For each feature:

1. **Write the test.** The test describes the expected behaviour. If you can't write the test, you don't understand the feature well enough — go back to the spec.
2. **Run the test. It should fail.** This confirms the test is actually testing something.
3. **Write the implementation.** Just enough to make the test pass.
4. **Run all tests.** Nothing broke.
5. **Lint. Build. Clean.**

### 4. Verify against the spec

After implementing a set of features, go back to the spec. Does the implementation match what was described? Did anything drift?

### 5. Discuss before the next batch

Before starting the next set of features, check in. Is the spec still right? Did we learn something during implementation that changes the plan?

## What this prevents

- **Building the wrong thing.** The spec is the agreement. If the spec is wrong, we find out before writing code.
- **Untested code.** Tests are written first. Coverage is a side effect of the process, not a goal.
- **Drift.** Regular check-ins against the spec catch divergence early.
- **Wasted work.** Discussing first means we don't build features that get thrown away.

## What this requires

- **Discipline.** The temptation is always to "just write the code." Resist it.
- **Short specs.** A spec that takes a week to write is too long. Write the minimum needed to agree on the behaviour.
- **Honest tests.** Tests that pass trivially or test implementation details instead of behaviour are worse than no tests.
