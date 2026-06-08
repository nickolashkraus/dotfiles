# Migrations

- Separate schema changes (DDL) and data changes (DML) into distinct
  migrations. DDL migrations handle structural changes (`CREATE TABLE`, `ALTER
  TABLE`, `ADD COLUMN`). DML migrations handle data operations (`INSERT`,
  `UPDATE`, `DELETE`). This allows each to land, fail, and roll back
  independently.
- When a rebase produces multiple Alembic heads, re-parent the branch's
  bottom-most migration onto the new tip in place. Do not add a no-op merge
  migration. The branch's migrations have not shipped yet, so editing
  `down_revision` is safe and keeps the production migration history linear.
  Reserve `alembic merge` migrations for the case where both chains have
  already been deployed and rewriting history is no longer an option.
- Never write an unbounded `UPDATE` or `DELETE` against a table with meaningful
  Prod row count. Chunk by primary-key range or `LIMIT`, with intermediate
  commits via `with op.get_context().autocommit_block():`. A single-statement
  multi-CTE `UPDATE` against a 100K+ row table can hold a transaction open for
  minutes, and that transaction interacts badly with migration-job timeouts and
  retry loops (see below).
- Measure backfill runtime against Prod row counts before merging. CI fixtures
  usually have zero or near-zero rows for the rows the backfill targets, so the
  CI runtime is meaningless. Query the read replica for the actual
  `WHERE`-clause match count, run `EXPLAIN (ANALYZE, BUFFERS)` on
  a representative sample, estimate runtime, and write the estimate into the PR
  body so reviewers can calibrate. If the estimate exceeds the migration-job
  timeout, the migration is not ready to merge.
- Set `lock_timeout` and `statement_timeout` at the start of every DDL
  migration:

  ```sql
  SET LOCAL lock_timeout = '5s';
  SET LOCAL statement_timeout = '5min';
  ```

  Without these, a DDL waiting for `AccessExclusiveLock` queues behind whatever
  holds the conflicting lock, and every new query queues behind the DDL waiter.
  Postgres lock queueing is FIFO, so one stalled `ALTER TABLE` becomes
  a service-wide outage on a busy table. A short `lock_timeout` makes the
  migration bail fast and retry instead of blocking the world.
- Use `CREATE INDEX CONCURRENTLY` for indexes on tables that exist in Prod.
  Alembic wraps each migration in a transaction by default, and `CONCURRENTLY`
  requires no enclosing transaction. Use `with
  op.get_context().autocommit_block():` to escape the wrapper:

  ```python
  def upgrade() -> None:
      with op.get_context().autocommit_block():
          op.create_index(
              "ix_foo_bar",
              "foo",
              ["bar"],
              postgresql_concurrently=True,
              if_not_exists=True,
          )
  ```

  The same applies to `DROP INDEX CONCURRENTLY`. To add a `UNIQUE` constraint
  on an existing table, build the index `CONCURRENTLY` first, then attach the
  constraint with `ALTER TABLE ... ADD CONSTRAINT ... USING INDEX`.
- For `NOT NULL` and `CHECK` constraints on existing tables, use the two-step
  `ADD CONSTRAINT ... NOT VALID` followed by a separate `VALIDATE CONSTRAINT`.
  The validation scan takes only `ShareUpdateExclusiveLock`, which permits
  reads and concurrent writes.
- Never combine slow DML with DDL in the same `alembic upgrade head`
  invocation. If the DML is killed by a job timeout, the retry runs from the
  top, and any DDL it hits takes `AccessExclusiveLock` while row locks from the
  previous run are still releasing. The AEL waits, and every incoming query
  queues behind it. Keep slow backfills in dedicated migrations that land and
  verify in their own release.
- Calibrate the migration-job timeout against the longest expected migration
  runtime, with margin. A job timeout shorter than the longest migration
  creates the retry-into-lock-queue trap above. An unbounded job timeout can
  let a runaway migration block Prod for minutes. The correct pair is
  a per-statement `statement_timeout` that bounds any single SQL statement,
  plus a job timeout sized for the full Alembic run.
- Run heavy migrations during low-traffic windows. A backfill that takes 60s
  when the table has 100 reads/sec running against it can take 10x longer when
  it has 10,000 reads/sec, because every conflicting reader serializes through
  the same row locks. Deployment guardrails should refuse risky migrations
  during peak hours.
- Treat two concurrent releases that both touch the same database as
  a release-process failure. Two simultaneous `alembic upgrade head`
  invocations doubles the lock-queue contention and turns a recoverable stall
  into a SEV0. Coordinate releases through the deployment channel and never
  assume "my migration is small" excuses overlapping with another deploy.
