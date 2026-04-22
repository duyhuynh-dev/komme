from __future__ import annotations

from collections import Counter

from app.ai.provider import StructuredModelProvider
from app.models.contracts import (
    CandidateEvent,
    InterestEvidence,
    InterestExtractionResult,
    InterestTopic,
    RankedCandidate,
    RankedCandidateList,
    RecommendationReasons,
    RetrievalPlan,
    RetrievalQuery,
)

KEYWORD_MAP = {
    "techno": ("underground_dance", "Underground dance"),
    "warehouse": ("underground_dance", "Underground dance"),
    "dj": ("underground_dance", "Underground dance"),
    "indie": ("indie_live_music", "Indie live music"),
    "gig": ("indie_live_music", "Indie live music"),
    "gallery": ("gallery_nights", "Gallery nights"),
    "opening": ("gallery_nights", "Gallery nights"),
    "meetup": ("creative_meetups", "Creative meetups"),
}


async def extract_interests(
    evidence: list[InterestEvidence],
    provider: StructuredModelProvider | None = None,
) -> InterestExtractionResult:
    if provider is not None:
        try:
            payload = "\n".join(
                f"- {item.activity_type} in r/{item.subreddit}: {item.text}" for item in evidence
            )
            return await provider.run(
                instructions=(
                    "Extract durable and recent event-related interests from Reddit evidence. "
                    "Return 3 to 8 concise topics with normalized keys, labels, confidence, and short evidence snippets."
                ),
                prompt=payload,
                output_type=InterestExtractionResult,
            )
        except RuntimeError:
            pass

    counts: Counter[tuple[str, str]] = Counter()
    signals: dict[tuple[str, str], list[str]] = {}
    for item in evidence:
        lowered = item.text.lower()
        for keyword, mapped in KEYWORD_MAP.items():
            if keyword in lowered or keyword in item.subreddit.lower():
                counts[mapped] += 1
                signals.setdefault(mapped, []).append(f"r/{item.subreddit}: {item.text[:80]}")

    topics = [
        InterestTopic(
            key=key,
            label=label,
            confidence=min(0.99, 0.55 + count * 0.1),
            signals=signals[(key, label)][:3],
        )
        for (key, label), count in counts.most_common(6)
    ]
    return InterestExtractionResult(topics=topics)


async def normalize_topics(
    topics: list[InterestTopic],
    provider: StructuredModelProvider | None = None,
) -> InterestExtractionResult:
    if provider is not None:
        try:
            prompt = "\n".join(f"- {topic.label}: {topic.signals}" for topic in topics)
            return await provider.run(
                instructions=(
                    "Normalize Pulse user interests into stable event-facing topics. "
                    "Merge duplicates and keep the strongest event-intent themes."
                ),
                prompt=prompt,
                output_type=InterestExtractionResult,
            )
        except RuntimeError:
            pass

    deduped: dict[str, InterestTopic] = {}
    for topic in topics:
        existing = deduped.get(topic.key)
        if existing is None or topic.confidence > existing.confidence:
            deduped[topic.key] = topic
    return InterestExtractionResult(topics=list(deduped.values()))


async def plan_queries(
    topics: list[InterestTopic],
    provider: StructuredModelProvider | None = None,
) -> RetrievalPlan:
    if provider is not None:
        try:
            prompt = "\n".join(f"- {topic.label} ({topic.confidence:.2f})" for topic in topics)
            return await provider.run(
                instructions=(
                    "Write targeted event retrieval queries for NYC culture discovery. "
                    "Queries should be source-aware and avoid generic broad search phrases."
                ),
                prompt=prompt,
                output_type=RetrievalPlan,
            )
        except RuntimeError:
            pass

    queries = [
        RetrievalQuery(query=f"{topic.label} NYC events", source="ticketmaster", category="culture")
        for topic in topics
    ]
    queries.extend(
        RetrievalQuery(query=f"{topic.label} Brooklyn venue calendar", source="curated_venues", category="culture")
        for topic in topics[:2]
    )
    return RetrievalPlan(queries=queries)


async def rerank_candidates(
    topics: list[InterestTopic],
    candidates: list[CandidateEvent],
    provider: StructuredModelProvider | None = None,
) -> RankedCandidateList:
    if provider is not None:
        try:
            prompt = (
                "Topics:\n"
                + "\n".join(f"- {topic.label} ({topic.confidence:.2f})" for topic in topics)
                + "\n\nCandidates:\n"
                + "\n".join(f"- {candidate.venue_name} | {candidate.title} | tags={candidate.tags}" for candidate in candidates)
            )
            return await provider.run(
                instructions=(
                    "Rerank venue-event candidates for a Pulse user. Prefer fit, freshness, practicality, and novelty. "
                    "Return 3 to 8 items with short rationale tags."
                ),
                prompt=prompt,
                output_type=RankedCandidateList,
            )
        except RuntimeError:
            pass

    scored_items: list[RankedCandidate] = []
    topic_terms = {topic.label.lower(): topic.confidence for topic in topics}
    for candidate in candidates:
        match_score = 0.35
        joined_text = " ".join([candidate.title, candidate.venue_name, candidate.neighborhood, *candidate.tags]).lower()
        for label, confidence in topic_terms.items():
            if any(term in joined_text for term in label.split()):
                match_score += confidence * 0.3
        match_score += candidate.source_confidence * 0.2
        if candidate.min_price is not None and candidate.min_price <= 75:
            match_score += 0.1
        score_band = "high" if match_score >= 0.8 else "medium" if match_score >= 0.55 else "low"
        scored_items.append(
            RankedCandidate(
                venue_name=candidate.venue_name,
                title=candidate.title,
                score=round(match_score, 3),
                score_band=score_band,
                reasons=[
                    "Taste overlap with recent Reddit behavior",
                    "Venue format and budget fit the current profile",
                ],
                tags=candidate.tags,
            )
        )
    scored_items.sort(key=lambda item: item.score, reverse=True)
    return RankedCandidateList(items=scored_items[:8])


async def write_reasons(
    topic: InterestTopic,
    candidate: CandidateEvent,
    provider: StructuredModelProvider | None = None,
) -> RecommendationReasons:
    if provider is not None:
        try:
            prompt = (
                f"Topic: {topic.label}\n"
                f"Candidate: {candidate.venue_name} - {candidate.title}\n"
                f"Tags: {candidate.tags}"
            )
            return await provider.run(
                instructions=(
                    "Write 2 short recommendation reasons for a consumer event app. "
                    "Keep them concrete, not mystical."
                ),
                prompt=prompt,
                output_type=RecommendationReasons,
            )
        except RuntimeError:
            pass

    return RecommendationReasons(
        reasons=[
            f"Selected because your current profile leans toward {topic.label.lower()} programming.",
            "This venue is a practical NYC option with a strong current candidate match.",
        ]
    )

