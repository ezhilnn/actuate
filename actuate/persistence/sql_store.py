"""PostgreSQL RunStore via SQLAlchemy 2.x + psycopg.

MySQL is not implemented — persistence target is Postgres only.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Float, String, Text, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from actuate.domain.control_system import ControlSystem, Workspace
from actuate.domain.events import Event
from actuate.domain.specification import Specification
from actuate.persistence.codec import decode_event, decode_specification, encode, encode_specification


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    at: Mapped[float] = mapped_column(Float)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SpecificationRow(Base):
    __tablename__ = "specifications"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    control_system_id: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


class WorkspaceRow(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[float] = mapped_column(Float)


class ControlSystemRow(Base):
    __tablename__ = "control_systems"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[float] = mapped_column(Float)


class KeyRow(Base):
    __tablename__ = "keychain"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    api_key: Mapped[str] = mapped_column(Text)


class GraphRunRow(Base):
    __tablename__ = "graph_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(String(32), default="running")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[float] = mapped_column(Float)


class SqlRunStore:
    def __init__(self, url: str) -> None:
        self.engine: AsyncEngine = create_async_engine(url, pool_pre_ping=True)
        self._session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def create_schema(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def append_event(self, event: Event) -> None:
        payload = encode(event)
        async with self._session() as session:
            session.add(
                EventRow(
                    id=event.id,
                    run_id=event.run_id,
                    at=event.at,
                    kind=type(event).__name__,
                    payload=payload,
                )
            )
            await session.commit()

    async def load_events(self, run_id: str) -> list[Event]:
        async with self._session() as session:
            rows = (
                await session.execute(
                    select(EventRow).where(EventRow.run_id == run_id).order_by(EventRow.at, EventRow.id)
                )
            ).scalars().all()
        return [decode_event(row.payload) for row in rows]

    async def save_specification(self, specification: Specification) -> None:
        payload = encode_specification(specification)
        async with self._session() as session:
            existing = await session.get(SpecificationRow, specification.id)
            if existing is None:
                session.add(
                    SpecificationRow(
                        id=specification.id,
                        control_system_id=specification.control_system_id,
                        payload=payload,
                    )
                )
            else:
                existing.payload = payload
                existing.control_system_id = specification.control_system_id
            await session.commit()

    async def load_specification(self, specification_id: str) -> Specification:
        async with self._session() as session:
            row = await session.get(SpecificationRow, specification_id)
        if row is None:
            raise KeyError(specification_id)
        return decode_specification(row.payload)

    async def list_specification_ids(self) -> list[str]:
        async with self._session() as session:
            rows = (await session.execute(select(SpecificationRow.id))).scalars().all()
        return list(rows)

    async def list_run_ids(self) -> list[str]:
        async with self._session() as session:
            rows = (await session.execute(select(EventRow.run_id).distinct())).scalars().all()
        return list(rows)

    async def save_workspace(self, workspace: Workspace) -> None:
        async with self._session() as session:
            existing = await session.get(WorkspaceRow, workspace.id)
            if existing is None:
                session.add(
                    WorkspaceRow(id=workspace.id, name=workspace.name, created_at=workspace.created_at)
                )
            else:
                existing.name = workspace.name
            await session.commit()

    async def list_workspaces(self) -> list[Workspace]:
        async with self._session() as session:
            rows = (await session.execute(select(WorkspaceRow))).scalars().all()
        return [Workspace(id=row.id, name=row.name, created_at=row.created_at) for row in rows]

    async def save_control_system(self, control_system: ControlSystem) -> None:
        async with self._session() as session:
            existing = await session.get(ControlSystemRow, control_system.id)
            if existing is None:
                session.add(
                    ControlSystemRow(
                        id=control_system.id,
                        workspace_id=control_system.workspace_id,
                        name=control_system.name,
                        description=control_system.description,
                        created_at=control_system.created_at,
                    )
                )
            else:
                existing.name = control_system.name
                existing.description = control_system.description
            await session.commit()

    async def list_control_systems(self, workspace_id: str | None = None) -> list[ControlSystem]:
        stmt = select(ControlSystemRow)
        if workspace_id is not None:
            stmt = stmt.where(ControlSystemRow.workspace_id == workspace_id)
        async with self._session() as session:
            rows = (await session.execute(stmt)).scalars().all()
        return [
            ControlSystem(
                id=row.id,
                workspace_id=row.workspace_id,
                name=row.name,
                description=row.description,
                created_at=row.created_at,
            )
            for row in rows
        ]

    async def put_key(self, provider: str, api_key: str) -> None:
        async with self._session() as session:
            existing = await session.get(KeyRow, provider)
            if existing is None:
                session.add(KeyRow(provider=provider, api_key=api_key))
            else:
                existing.api_key = api_key
            await session.commit()

    async def get_keys(self) -> dict[str, str]:
        async with self._session() as session:
            rows = (await session.execute(select(KeyRow))).scalars().all()
        return {row.provider: row.api_key for row in rows}

    async def save_graph_run(self, run: dict[str, Any]) -> None:
        import time

        async with self._session() as session:
            existing = await session.get(GraphRunRow, run["id"])
            if existing is None:
                session.add(
                    GraphRunRow(
                        id=run["id"],
                        name=str(run.get("name") or run.get("graph_name") or ""),
                        status=str(run.get("status") or "running"),
                        payload=run,
                        created_at=time.time(),
                    )
                )
            else:
                existing.payload = run
                existing.status = str(run.get("status") or existing.status)
                existing.name = str(run.get("name") or existing.name)
            await session.commit()

    async def load_graph_run(self, run_id: str) -> dict[str, Any] | None:
        async with self._session() as session:
            row = await session.get(GraphRunRow, run_id)
        return dict(row.payload) if row is not None else None

    async def list_graph_runs(self) -> list[dict[str, Any]]:
        async with self._session() as session:
            rows = (await session.execute(select(GraphRunRow).order_by(GraphRunRow.created_at.desc()))).scalars().all()
        return [dict(row.payload) for row in rows]
