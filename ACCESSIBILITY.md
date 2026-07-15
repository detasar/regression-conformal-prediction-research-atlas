# Accessibility

This Research Atlas is built as a static HTML publication surface. The main public pages are designed for keyboard navigation, semantic reading order, and screen-reader inspection of the article, supplement, Research Document, result explorer, provenance tables, and knowledge graph fallback tables.

## Current Support

- Public HTML pages include a main landmark, skip link, visible focus styles, page titles, descriptions, canonical links, and structured metadata.
- Tables include captions and scoped header cells.
- Interactive result and provenance panels announce updates with polite status regions.
- The knowledge graph browser includes search, route controls, one-hop and two-hop controls, status messages, a legend, and table fallbacks for graph routes and selected neighborhoods.
- The site can be read without credentials, external scripts, or third-party tracking assets.

## Known Limits

- The graph canvas remains a visual exploration aid; the fallback tables are the accessible source-inspection path.
- PDF tagging and formal PDF/UA validation are not complete in the current version.
- Automated axe or Lighthouse accessibility reports are outside the current public CI path.

## Feedback

Accessibility issues can be reported to Emre Tasar at <detasar@gmail.com>. Please include the affected page, browser or assistive technology if relevant, and a short description of the barrier.

Last updated: 2026-07-15
