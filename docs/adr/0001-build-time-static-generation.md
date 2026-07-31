# ADR 0001: Generate the conformity page at build time

**Status:** Accepted
**Date:** 2026-07-31

## Context

The packaging conformity declaration lives in a spreadsheet that changes
whenever packaging is added or altered. It must be published publicly in German
and English, and read from a phone by anyone who scans a QR code on a package
anywhere in the EU. The German source text is free text with a small, highly
repetitive vocabulary.

## Decision

A build step converts the spreadsheet into complete static HTML for both
languages, run by GitHub Actions on every push and deployed to GitHub Pages.
Translation is driven by a glossary in the repository. Any term the glossary
cannot resolve fails the build.

## Consequences

The published page is inert HTML: it works with JavaScript disabled, prints
cleanly, and cannot render a half-translated table, because a build that cannot
translate everything never produces artefacts to deploy. The previously
published site stays live while the glossary is corrected.

The cost is a glossary that must be extended when genuinely new packaging
vocabulary appears. Given the vocabulary of the current range — 13 terms and 7
patterns cover all 19 articles — this is a small, and deliberately visible,
maintenance burden.

## Alternatives considered

**Parse the spreadsheet in the browser.** Ship the xlsx and read it with
SheetJS. Requires no build step at all. Rejected: it puts roughly 400 KB of
JavaScript in front of someone scanning a box, moves translation to the client
where an unknown term silently renders German, and nothing validates the file
before it is public.

**Commit a generated JSON file.** Convert the spreadsheet to JSON in CI, commit
it, and fetch it from the page. Gives a reviewable diff of every data change.
Rejected: it puts bot commits on `main` and makes page content depend on
JavaScript. The diff benefit is recovered by having the build log the article
count it produced.
