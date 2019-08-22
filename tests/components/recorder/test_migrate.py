"""The tests for the Recorder component."""
# pylint: disable=protected-access
from unittest.mock import patch, call

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.recorder import (
    migration, const, models)
from tests.components.recorder import models_original


def create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    engine = create_engine(*args, **kwargs)
    models_original.Base.metadata.create_all(engine)
    return engine


async def test_schema_update_calls(hass):
    """Test that schema migrations occur in correct order."""
    with patch('sqlalchemy.create_engine', new=create_engine_test), \
        patch('homeassistant.components.recorder.migration._apply_update') as \
            update:
        await async_setup_component(hass, 'recorder', {
            'recorder': {
                'db_url': 'sqlite://'
            }
        })
        await hass.async_block_till_done()

    update.assert_has_calls([
        call(hass.data[const.DATA_INSTANCE].engine, version+1, 0) for version
        in range(0, models.SCHEMA_VERSION)])


async def test_schema_migrate(hass):
    """Test the full schema migration logic.

    We're just testing that the logic can execute successfully here without
    throwing exceptions. Maintaining a set of assertions based on schema
    inspection could quickly become quite cumbersome.
    """
    with patch('sqlalchemy.create_engine', new=create_engine_test), \
        patch('homeassistant.components.recorder.Recorder._setup_run') as \
            setup_run:
        await async_setup_component(hass, 'recorder', {
            'recorder': {
                'db_url': 'sqlite://'
            }
        })
        await hass.async_block_till_done()
        assert setup_run.called


def test_invalid_update():
    """Test that an invalid new version raises an exception."""
    with pytest.raises(ValueError):
        migration._apply_update(None, -1, 0)


def test_forgiving_add_column():
    """Test that add column will continue if column exists."""
    engine = create_engine(
        'sqlite://',
        poolclass=StaticPool
    )
    engine.execute('CREATE TABLE hello (id int)')
    migration._add_columns(engine, 'hello', [
        'context_id CHARACTER(36)',
    ])
    migration._add_columns(engine, 'hello', [
        'context_id CHARACTER(36)',
    ])


def test_forgiving_add_index():
    """Test that add index will continue if index exists."""
    engine = create_engine(
        'sqlite://',
        poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    migration._create_index(engine, "states", "ix_states_context_id")
