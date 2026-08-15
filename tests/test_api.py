import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from actuate.api.app import app


@pytest.mark.asyncio
async def test_health_and_stub_run() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        assert health.status_code == 200
        models = await client.get("/api/models")
        assert models.status_code == 200
        assert all(p["id"] != "stub" for p in models.json()["providers"])
        caps = await client.get("/api/capabilities")
        assert all(not (c["kind"] == "plant" and c["name"] == "stub") for c in caps.json()["capabilities"])
        designer = await client.get("/api/designer")
        assert designer.status_code == 200
        blocked = await client.post(
            "/api/runs",
            json={"prompt": "x", "provider": "stub", "model": "stub/local"},
        )
        assert blocked.status_code == 400
        started = await client.post(
            "/api/runs",
            json={
                "prompt": "Write a short answer.",
                "provider": "stub",
                "model": "stub/local",
                "required_phrases": ["MUST-INCLUDE"],
                "max_iterations": 5,
                "retry_strategy": "none",
                "allow_stub": True,
            },
        )
        assert started.status_code == 200
        run_id = started.json()["run_id"]
        detail = await client.get(f"/api/runs/{run_id}")
        for _ in range(40):
            detail = await client.get(f"/api/runs/{run_id}")
            if detail.json().get("status") not in {"pending", "running"}:
                break
            await asyncio.sleep(0.05)
        assert detail.json()["iterations"]
