from actuate.persistence.in_memory_store import InMemoryRunStore

__all__ = ["InMemoryRunStore", "SqlRunStore"]


def __getattr__(name: str):
    if name == "SqlRunStore":
        from actuate.persistence.sql_store import SqlRunStore

        return SqlRunStore
    raise AttributeError(name)
