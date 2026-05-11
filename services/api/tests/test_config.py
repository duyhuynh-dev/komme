from app.core.config import Settings


def test_allowed_web_origins_include_localhost_and_loopback_aliases() -> None:
    settings = Settings(
        web_app_url="http://localhost:3000",
        web_allowed_origins="https://komme.example.com",
    )

    assert settings.allowed_web_origins == [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "https://komme.example.com",
    ]


def test_allowed_web_origins_include_komme_domain_aliases() -> None:
    settings = Settings(
        web_app_url="https://komme.xyz",
        web_allowed_origins="https://www.komme.xyz,https://pulse-app.duckdns.org",
    )

    assert settings.allowed_web_origins == [
        "https://komme.xyz",
        "https://pulse-app.duckdns.org",
        "https://www.komme.xyz",
    ]
