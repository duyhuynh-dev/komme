from app.ai.provider import StructuredModelProvider
from app.ai.tasks import extract_interests, normalize_topics
from app.models.contracts import InterestEvidence, InterestExtractionResult


async def build_interest_profile(
    evidence: list[InterestEvidence],
    provider: StructuredModelProvider | None = None,
) -> InterestExtractionResult:
    extracted = await extract_interests(evidence, provider)
    return await normalize_topics(extracted.topics, provider)

