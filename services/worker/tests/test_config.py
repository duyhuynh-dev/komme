from app.core.config import Settings


def test_trusted_hosts_include_worker_aliases_and_internal_health_hosts() -> None:
    settings = Settings(worker_allowed_hosts="worker.komme.xyz,pulse-worker.duckdns.org,worker")

    assert settings.trusted_hosts == [
        "127.0.0.1",
        "localhost",
        "pulse-worker.duckdns.org",
        "testserver",
        "worker",
        "worker.komme.xyz",
    ]
