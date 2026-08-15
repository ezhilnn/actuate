import pytest

from actuate.persistence.bootstrap import BOOTSTRAP_WORKSPACE_ID, seed_store
from actuate.persistence.in_memory_store import InMemoryRunStore


@pytest.mark.asyncio
async def test_bootstrap_is_idempotent() -> None:
    store = InMemoryRunStore()
    first = await seed_store(store)
    second = await seed_store(store)
    assert first.id == second.id == BOOTSTRAP_WORKSPACE_ID
    systems = await store.list_control_systems()
    assert {s.id for s in systems} >= {"cs_offline_stub", "cs_nvidia_nim", "cs_custom_endpoint"}
    specs = await store.list_specification_ids()
    assert "spec_offline_stub" in specs
    keys = await store.get_keys()
    assert keys["nvidia_base"].startswith("https://integrate.api.nvidia.com")
    await seed_store(store)
    assert len(await store.list_control_systems()) == len(systems)
