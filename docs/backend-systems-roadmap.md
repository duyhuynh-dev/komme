# Backend Systems Roadmap

This roadmap turns the current "good demo" into a more trustworthy and more explainable product without overbuilding too early.

## Phase 1: Trust Layer

Goal: make Pulse explain what it is doing before we make it more complex.

Slices:

1. Service-area and anchor transparency
   - expose which anchor is actually active
   - explain when a live location falls back to a saved NYC anchor
   - stop silent CT -> East Village behavior

2. Recommendation freshness and provenance
   - show when the map was generated
   - expose source/provider confidence per surfaced event
   - carry source provenance through ingestion

3. Why-this-for-me clarity
   - make recommendation reasons more specific
   - distinguish observed behavior, inferred taste, and feedback-derived boosts

## Phase 2: Recommendation Engine V2

Goal: move from opaque heuristics to auditable ranking.

Slices:

1. feature-logged recommendation runs
2. explicit score components
3. run context hashing and versioning
4. replay / offline comparison tooling

## Phase 3: Supply Quality

Goal: make the catalog more reliable than a stitched-together feed.

Slices:

1. raw source events vs canonical events
2. venue alias resolution and dedupe
3. source trust scoring
4. ingestion retry / dead-letter handling

## Phase 4: Feedback Learning

Goal: let real user behavior shape ranking.

Slices:

1. richer controls than save / dismiss
2. exploration vs exploitation rules
3. behavior-weighted theme confidence
4. ranking evaluation from user outcomes

## Immediate next build order

1. Service-area and anchor transparency
2. Recommendation freshness/provenance payloads
3. Recommendation run explainability
4. Expanded feedback controls
