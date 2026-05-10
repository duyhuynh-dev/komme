from app.connectors.curated_venues import (
    ARTISTS_AND_FLEAS,
    CURATED_SOURCES,
    NINETYTWO_Y,
    PIONEER_WORKS,
    PUBLIC_RECORDS,
    _parse_json_ld_events,
    _parse_ninetytwo_y_events,
    _parse_pioneer_works_calendar,
    _parse_public_records_html,
)


PUBLIC_RECORDS_HTML = """
<html>
  <body>
    <a href="https://link.dice.fm/public-records-ambient">
      Wed 4.22 Live, 7:00 pm, Sound Room International Anthem presents: Gregory Uhlmann Extra Stars Release Show Get tickets
    </a>
  </body>
</html>
"""

PIONEER_WORKS_CALENDAR_HTML = """
<html>
  <body>
    <div>SATURDAY, APRIL 25</div>
    <a href="/programs/clan-of-xymox-cold-cave">Clan of Xymox, Cold Cave program</a>
  </body>
</html>
"""

PIONEER_WORKS_DETAIL_HTML = """
<html>
  <head>
    <meta name="description" content="A darkwave concert program at Pioneer Works." />
  </head>
  <body>
    <div>Start: April 25, 2026 | 8:00 pm</div>
  </body>
</html>
"""

JSON_LD_EVENTS_HTML = """
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {
            "@type": "BusinessEvent",
            "name": "Collector Market Weekend Floor",
            "description": "A vintage market with design vendors and collector-friendly stalls.",
            "startDate": "2026-05-02T12:00:00-04:00",
            "endDate": "2026-05-02T16:00:00-04:00",
            "url": "https://example.com/collector-market",
            "keywords": ["vintage", "design market", "popup"],
            "offers": [
              {"price": "12"},
              {"price": "18"}
            ]
          }
        ]
      }
    </script>
  </head>
</html>
"""

NINETYTWO_Y_HTML = """
<html>
  <body>
    <div>Featured Events at 92NY</div>
    <div>In Person</div>
    <div>May 6 | 7:00 PM</div>
    <div>The Future of Being Jewish in New York: Julie Menin in Conversation</div>
    <a href="https://www.92ny.org/event/future-of-being-jewish">View More</a>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    async def get(self, url: str) -> FakeResponse:
        assert url.endswith("/programs/clan-of-xymox-cold-cave")
        return FakeResponse(PIONEER_WORKS_DETAIL_HTML)


def test_curated_sources_cover_more_real_nyc_venues() -> None:
    source_keys = {source.key for source in CURATED_SOURCES}

    assert len(CURATED_SOURCES) >= 8
    assert {"house-of-yes", "knockdown-center", "nublu"}.issubset(source_keys)


def test_parse_public_records_html_extracts_candidate() -> None:
    candidates = _parse_public_records_html(PUBLIC_RECORDS_HTML, PUBLIC_RECORDS)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.venue_name == "Public Records"
    assert candidate.title.startswith("International Anthem presents")
    assert candidate.ticket_url == "https://link.dice.fm/public-records-ambient"
    assert candidate.source_url == "https://link.dice.fm/public-records-ambient"
    assert candidate.source_base_url == PUBLIC_RECORDS.listing_url
    assert candidate.category == "live music"


async def test_parse_pioneer_works_calendar_enriches_with_detail_page() -> None:
    candidates = await _parse_pioneer_works_calendar(
        FakeClient(),
        PIONEER_WORKS_CALENDAR_HTML,
        PIONEER_WORKS,
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.venue_name == "Pioneer Works"
    assert candidate.title == "Clan of Xymox, Cold Cave"
    assert candidate.category == "live music"
    assert candidate.ticket_url.endswith("/programs/clan-of-xymox-cold-cave")
    assert "Pioneer Works" in candidate.summary


def test_parse_json_ld_events_extracts_broader_cultural_candidate() -> None:
    candidates = _parse_json_ld_events(JSON_LD_EVENTS_HTML, ARTISTS_AND_FLEAS)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.venue_name == "Artists & Fleas Williamsburg"
    assert candidate.category == "market"
    assert candidate.ticket_url == "https://example.com/collector-market"
    assert candidate.source_url == "https://example.com/collector-market"
    assert candidate.source_base_url == ARTISTS_AND_FLEAS.listing_url
    assert candidate.min_price == 12
    assert candidate.max_price == 18
    assert "collector_marketplaces" in candidate.topic_keys
    assert "style_design_shopping" in candidate.topic_keys


def test_parse_ninetytwo_y_events_extracts_talk_candidate() -> None:
    candidates = _parse_ninetytwo_y_events(NINETYTWO_Y_HTML, NINETYTWO_Y)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.venue_name == "92NY"
    assert candidate.category == "talk"
    assert candidate.ticket_url == "https://my.92ny.org/events"
    assert "student_intellectual_scene" in candidate.topic_keys
