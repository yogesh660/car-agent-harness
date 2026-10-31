# 0005 - Tools depend on a small read-only database interface

Status: accepted (2026-11)

## Context

M2 moves runtime listings to PostgreSQL while keeping SQLite for fast, isolated tests. The tools
previously accepted `sqlite3.Connection` directly, which made the storage choice part of every tool
signature and domain row.

## Decision

Marketplace tools depend on the `ReadConnection`, `QueryResult` and `DataRow` protocols in
`car_agent.db`. These protocols contain only the read operations the tools use. SQLite remains the
default implementation and continues to open in read-only mode.

PostgreSQL support will be added behind the same interface. Driver selection, placeholder
adaptation and connection lifecycle belong in `car_agent.db`, outside tool business logic.

## Consequences

- Tool functions and domain models no longer import SQLite.
- Existing tests keep using the deterministic SQLite database.
- A PostgreSQL adapter can be added without changing tool inputs, outputs or agent wrappers.
- The interface deliberately excludes writes; seeding remains a separate data operation.
