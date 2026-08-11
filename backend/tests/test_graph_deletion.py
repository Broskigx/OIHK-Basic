from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app import models
from app.core.deps import CurrentUser
from app.database import Base
from app.routers.graph import delete_graph_entity


@pytest.mark.asyncio
async def test_graph_entity_deletion_is_authorized_and_removes_relationships(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'graph-delete.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    owner = models.User(
        email="owner@example.test",
        username="owner",
        hashed_password="not-used",
        role="analyst",
        organization_id="alpha",
    )
    outsider = models.User(
        email="outsider@example.test",
        username="outsider",
        hashed_password="not-used",
        role="analyst",
        organization_id="bravo",
    )
    async with sessions() as session:
        session.add_all([owner, outsider])
        await session.flush()
        case = models.Case(
            owner_id=owner.id,
            organization_id="alpha",
            title="Authorized graph",
            legal_basis="Authorized test",
            scope_statement="Bounded test scope",
        )
        session.add(case)
        await session.flush()
        first = models.Entity(case_id=case.id, type="email", value="one@example.test", display="one@example.test")
        second = models.Entity(case_id=case.id, type="domain", value="example.test", display="example.test")
        session.add_all([first, second])
        await session.flush()
        relationship = models.Relationship(
            case_id=case.id,
            subject_id=first.id,
            predicate="uses",
            object_id=second.id,
        )
        session.add(relationship)
        await session.commit()

        outsider_context = CurrentUser(
            id=outsider.id,
            email=outsider.email,
            username=outsider.username,
            role=outsider.role,
            organization_id=outsider.organization_id,
        )
        with pytest.raises(HTTPException) as denied:
            await delete_graph_entity(first.id, outsider_context, session)
        assert denied.value.status_code == 403
        assert await session.get(models.Entity, first.id) is not None

        owner_context = CurrentUser(
            id=owner.id,
            email=owner.email,
            username=owner.username,
            role=owner.role,
            organization_id=owner.organization_id,
        )
        result = await delete_graph_entity(first.id, owner_context, session)
        assert result == {"deleted": True, "entity_id": first.id, "relationship_count": 1}
        assert await session.get(models.Entity, first.id) is None
        assert (await session.execute(select(models.Relationship))).scalars().all() == []

    await engine.dispose()
