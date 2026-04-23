from app.core.config import Settings


def test_allowed_web_origins_include_localhost_and_loopback_aliases() -> None:
    settings = Settings(
        web_app_url="http://localhost:3000",
        web_allowed_origins="https://pulse.example.com",
    )

    assert settings.allowed_web_origins == [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "https://pulse.example.com",
    ]
