---
id: 2
title: A CSS-selector change is only verified against a rendered page
status: open
type: open-source
skill: [superpowers:verification-before-completion]
proposes_skill: []
siblings_checked: "no skill-families.md registry present; superpowers:test-driven-development evaluated by hand and excluded — the point is not that a test should have been written first but that no unit test can observe this class of change at all, which is a verification-evidence rule."
area: what counts as evidence for a change
date: 2026-09-03
session_context: Finishing uncommitted UI work whose last edit had rewritten CSS selectors for a UI framework's changed DOM
---

**Issue:** The last edit of the previous session rewrote CSS selectors
because the UI framework had replaced its component library and the old
`div[data-*]` hooks no longer existed in the DOM. Nothing in the test suite
can observe that: the selectors are strings in a stylesheet, so both the
old broken ones and the new ones pass every test identically. Lint and the
suite were both green while the styling was, by the author's own note,
visibly broken in the running app.

**Suggested improvement:** In the verification skill, list the change types
whose evidence cannot come from the test suite — CSS selectors, styling,
layout, positioning, anything matched against a DOM the framework owns —
and require the evidence to be a rendered page (screenshot or DOM query)
before such a change may be called verified. Note the specific trap: a
framework version bump can silently invalidate every selector without a
single failing test.

**Principle:** Evidence has to be capable of contradicting the claim. For a
change whose whole effect is on rendered output, a passing test suite
cannot contradict anything, so it is not evidence — only looking at the
rendered result is.
