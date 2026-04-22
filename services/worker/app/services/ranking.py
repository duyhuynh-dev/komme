from app.models.contracts import CandidateEvent, InterestTopic, RankedCandidateList
from app.ai.tasks import rerank_candidates
from app.ai.provider import StructuredModelProvider


def combine_score(
    *,
    fit_score: float,
    profile_confidence: float,
    event_quality: float,
    source_confidence: float,
    novelty: float,
) -> float:
    total = (
        fit_score * 0.5
        + profile_confidence * 0.2
        + event_quality * 0.1
        + source_confidence * 0.1
        + novelty * 0.1
    )
    return round(max(0.0, min(total, 1.0)), 3)


async def rank_candidates(
    topics: list[InterestTopic],
    candidates: list[CandidateEvent],
    provider: StructuredModelProvider | None = None,
) -> RankedCandidateList:
    return await rerank_candidates(topics, candidates, provider)

