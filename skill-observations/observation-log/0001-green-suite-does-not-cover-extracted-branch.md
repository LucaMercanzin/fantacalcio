---
id: 1
title: A green suite after an extraction can mean the new branch is never reached
status: open
type: open-source
skill: [superpowers:verification-before-completion, superpowers:test-driven-development]
proposes_skill: []
siblings_checked: "no skill-families.md registry present; both superpowers testing/verification skills evaluated by hand — the insight is about what a passing suite proves, so it belongs to the verification skill primarily and to TDD as the rule for the extraction step itself. superpowers:requesting-code-review considered and excluded: it is about soliciting review, not about coverage inference."
area: interpreting a passing test suite after refactoring
date: 2026-09-03
session_context: Resuming uncommitted dashboard work; a function holding the auction purchase flow had been split into two, and the whole suite passed
---

**Issue:** A large function was split into a "bar" part and a "details"
part, with a new return-value contract between them. The full suite passed
unchanged, which reads as evidence the refactor is safe. It was not: the
single fixture exercising that page set a flag that short-circuits the code
at the very top of the extracted function, so neither the new interactive
branch nor the new contract between the two halves was ever executed. The
green suite was measuring the early-return path only.

**Suggested improvement:** In the verification skill's evidence rules, add
that "the suite still passes" is not evidence for extracted or newly split
code until you have confirmed the tests actually reach it — the cheap check
is to read the fixture's inputs for a flag or default that returns early,
or to break the new code deliberately and confirm a test fails. In the TDD
skill, add the same check to the refactor step: an extraction with no test
that enters it is untested code, regardless of suite colour.

**Principle:** A passing suite proves the paths the tests enter, not the
paths the code contains. After moving code behind a new entry point, the
question is not "do the tests still pass" but "does any test reach the code
I moved" — and a fixture's default values are the usual reason the answer
is no.
