from app.taste.profile_contracts import ThemeCatalogItem

THEME_CATALOG: list[ThemeCatalogItem] = [
    ThemeCatalogItem(
        id="underground_dance",
        label="Underground dance",
        description="Warehouse sets, techno, rave nights, and left-of-mainstream dance floors.",
    ),
    ThemeCatalogItem(
        id="indie_live_music",
        label="Indie live music",
        description="Intimate rooms, touring bands, singer-songwriters, and alt-pop bills.",
    ),
    ThemeCatalogItem(
        id="gallery_nights",
        label="Gallery nights",
        description="Art openings, installations, and neighborhood gallery crawls.",
    ),
    ThemeCatalogItem(
        id="jazz_intimate_shows",
        label="Jazz / intimate shows",
        description="Listening rooms, small ensembles, and musically focused late evenings.",
    ),
    ThemeCatalogItem(
        id="hiphop_rap_shows",
        label="Hip-hop / rap shows",
        description="Rap nights, beat showcases, and high-energy live performances.",
    ),
    ThemeCatalogItem(
        id="comedy_nights",
        label="Comedy",
        description="Stand-up, alt-comedy, and independent comedy rooms.",
    ),
    ThemeCatalogItem(
        id="dive_bar_scene",
        label="Dive bars / local scene",
        description="Neighborhood bars, low-key nights, and local regular spots.",
    ),
    ThemeCatalogItem(
        id="rooftop_lounges",
        label="Rooftop / upscale lounges",
        description="Views, polished spaces, and social nights with a dressed-up feel.",
    ),
    ThemeCatalogItem(
        id="late_night_food",
        label="Late-night food scene",
        description="Food pop-ups, late bites, and destination restaurants worth planning around.",
    ),
    ThemeCatalogItem(
        id="queer_nightlife",
        label="Queer nightlife",
        description="Queer clubs, drag, community-centered parties, and inclusive social nights.",
    ),
]

THEME_CATALOG_BY_ID = {theme.id: theme for theme in THEME_CATALOG}
