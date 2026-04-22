from app.ai.provider import StructuredModelProvider
from app.ai.tasks import plan_queries, write_reasons
from app.connectors.curated_venues import CuratedVenueConnector
from app.connectors.ticketmaster import TicketmasterConnector
from app.models.contracts import CandidateEvent, InterestEvidence, RankedCandidateList
from app.services.profile_builder import build_interest_profile
from app.services.ranking import rank_candidates


async def run_recommendation_pipeline(evidence: list[InterestEvidence]) -> RankedCandidateList:
    provider = StructuredModelProvider()
    profile = await build_interest_profile(evidence, provider)
    plan = await plan_queries(profile.topics, provider)

    connectors = {
        "ticketmaster": TicketmasterConnector(),
        "curated_venues": CuratedVenueConnector(),
    }

    candidates: list[CandidateEvent] = []
    for query in plan.queries:
        connector = connectors.get(query.source)
        if connector is None:
            continue
        candidates.extend(await connector.search(query))

    ranked = await rank_candidates(profile.topics, candidates, provider)
    if profile.topics and candidates:
        await write_reasons(profile.topics[0], candidates[0], provider)
    return ranked

