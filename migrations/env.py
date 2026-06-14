from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from ccld_complaints.hosted_app.persistence import (
    HostedDatabaseConfigError,
    load_hosted_database_config,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _set_database_url_from_environment() -> str:
    try:
        database_config = load_hosted_database_config(require_url=True)
    except HostedDatabaseConfigError as error:
        raise RuntimeError(str(error)) from error
    if database_config.database_url is None:
        raise RuntimeError("Set the hosted tester database URL before running migrations.")
    config.set_main_option("sqlalchemy.url", database_config.database_url)
    return database_config.database_url


def run_migrations_offline() -> None:
    database_url = _set_database_url_from_environment()
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _set_database_url_from_environment()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()