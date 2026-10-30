# Repair portable device-code lookup indexing

This checkout is a real Better Auth TypeScript monorepo. Device authorization repeatedly looks up `deviceCode` and `userCode`, but the plugin does not declare their lookup indexes. The documentation schema copier also drops non-unique field index hints. Complete this feature across the existing schema, migration and schema-generation boundaries.

Work in `/app/repo`. Dependencies are installed from the committed lockfile with pnpm 11.1.1. Use the existing TypeScript APIs and preserve authentication behavior. Do not add packages or change dependency versions. Your final production source tree is collected automatically.

## Required behavior

1. Fresh and upgraded SQLite device-authorization storage must have non-unique indexes on both lookup fields. Keep existing rows and unique constraints. Running the migration again after applying it must report no further changes. Use the repository's existing migration contract rather than introducing a parallel database system.
2. The `DBFieldAttribute` input accepted by `docs/lib/copy-schema` must support an optional boolean `index` hint. The `copySchema` result must preserve non-unique index meaning in SQLite, PostgreSQL, MySQL and SQL Server output, in both create and alter modes. A field that is already unique must not receive a redundant non-unique index. Fields removed by a false schema condition must not leave indexes behind.
3. Generated SQLite create-mode DDL must run twice without an index-already-exists error. MySQL and SQL Server index statements must guard creation by the existence of the target table and index. In MySQL, use the `information_schema.tables` and `information_schema.statistics` catalogs; in SQL Server use the target object's `sys.indexes` entries. Escape single quotes in catalog string literals. These provider-specific catalogs are part of this task's output contract. No live MySQL or SQL Server instance is required.
4. Indexed MySQL strings must use a portable 191-character bound rather than unbounded text. A generated string-index prefix, if used, must preserve that bound. Indexed SQL Server strings must remain bounded, at most 255 characters, rather than using an unbounded/text-sized column. Preserve existing type selection for other fields.
5. Prisma and Drizzle schema output must retain the same non-unique index meaning, including the existing field-name mapping rules. Do not add a second non-unique index for unique fields. MySQL Drizzle output must use bounded indexed strings.
6. Generated index names must be deterministic, distinct for different field names with the same long prefix, and consistent across the SQL dialects. Keep names within 63 UTF-8 bytes without splitting a Unicode code point. A truncated name still needs a stable suffix derived from the complete original name, rather than collapsing both names to the same prefix. Do not measure this budget in JavaScript UTF-16 code units.
7. Device and user code length options must reject values above 191. Validate the results of custom code generators before storing a device authorization request. A non-string or a string longer than 191 Unicode code points must produce an `invalid_request` API error with no device-code row written. Both synchronous and asynchronous generators remain supported. A 191-code-point value containing astral Unicode characters must remain valid.

## Preserve working behavior

Existing device authorization, verification, approval, denial, ownership checks, no-store responses, polling and custom-option behavior must continue to work. Existing SQLite migrations for added indexed columns, custom names and repeated migration detection must remain valid.

The verifier uses the real APIs and a real in-process SQLite database. Other database engines are checked through the generated SQL or schema representation. It does not grade a live connection to those engines. The verifier accepts equivalent production implementations that meet the stated contracts.

## Public checks

```sh
cd /app/repo
pnpm exec vitest run --config vitest.task.config.ts
```

This runs 50 preserved upstream checks, including the device authorization suite and the SQLite-only migration cases. The task configuration resolves local workspace packages from source while resolving published packages from their distributed builds. The nine PostgreSQL-only migration cases requiring an external service are excluded from this public task selection. They are not silently counted as passing.

Hidden checks exercise the indexing feature, real SQLite migration and DDL execution, generator outputs, identifier boundaries and invalid custom generator results. They also compile the focused schema-generator type contract. You do not receive the hidden test code or reference fix during the coding trial.

## Submission boundary

Only production `.ts` and `.tsx` files under `packages/better-auth/src`, `packages/core/src`, and `docs/lib/copy-schema` are applied to the clean verifier checkout. Test files, package manifests, lockfiles, Vitest configuration, dependency directories, Git metadata and other workspace edits are not accepted as fixes. You may create your own local scratch tests, but the verifier restores its original tests and private cases independently.
