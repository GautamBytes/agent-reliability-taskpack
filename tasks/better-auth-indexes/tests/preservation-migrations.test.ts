import { DatabaseSync } from "node:sqlite";
import type { BetterAuthOptions } from "@better-auth/core";
import {describe,expect,it} from "vitest";
import {getMigrations} from "../packages/better-auth/src/db/get-migration";
describe("index generation for columns added to existing tables", () => {
	it("should use CREATE INDEX when adding indexed columns to existing SQLite tables", async () => {
		const config: BetterAuthOptions = {
			database: new DatabaseSync(":memory:"),
			emailAndPassword: {
				enabled: true,
			},
		};

		const initial = await getMigrations(config);
		await initial.runMigrations();

		config.plugins = [
			{
				id: "test-index",
				schema: {
					user: {
						fields: {
							externalId: {
								type: "string",
								index: true,
								required: false,
							},
						},
					},
				},
			},
		];

		const { compileMigrations } = await getMigrations(config);
		const sql = (await compileMigrations()).toLowerCase();

		expect(sql).toContain("create index");
		expect(sql).not.toContain("add index");
	});

	/**
	 * @see https://github.com/better-auth/better-auth/issues/10356
	 */
	it("should enforce unique indexed fields on new tables without a duplicate index", async () => {
		const db = new DatabaseSync(":memory:");
		const config: BetterAuthOptions = {
			database: db,
			emailAndPassword: {
				enabled: true,
			},
			plugins: [
				{
					id: "test-unique-index",
					schema: {
						uniqueTable: {
							fields: {
								slug: {
									type: "string",
									index: true,
									unique: true,
									required: true,
								},
							},
						},
					},
				},
			],
		};

		const { compileMigrations, runMigrations } = await getMigrations(config);
		const sql = (await compileMigrations()).toLowerCase();

		expect(sql).toMatch(
			/create table "uniquetable"[^;]*"slug" text not null unique/s,
		);
		expect(sql).not.toContain("uniquetable_slug_uidx");

		await runMigrations();
		db.exec(
			`INSERT INTO "uniqueTable" ("id", "slug") VALUES ('first', 'shared')`,
		);
		expect(() =>
			db.exec(
				`INSERT INTO "uniqueTable" ("id", "slug") VALUES ('second', 'shared')`,
			),
		).toThrow();
	});

	/**
	 * @see https://github.com/better-auth/better-auth/issues/9689
	 */
	it("should execute runMigrations without error when adding indexed columns to existing tables", async () => {
		const config: BetterAuthOptions = {
			database: new DatabaseSync(":memory:"),
			emailAndPassword: {
				enabled: true,
			},
		};

		const initial = await getMigrations(config);
		await initial.runMigrations();

		config.plugins = [
			{
				id: "test-index",
				schema: {
					user: {
						fields: {
							externalId: {
								type: "string",
								index: true,
								required: false,
							},
						},
					},
				},
			},
		];

		const { runMigrations } = await getMigrations(config);
		await expect(runMigrations()).resolves.not.toThrow();
	});

	/**
	 * @see https://github.com/better-auth/better-auth/issues/9689
	 */
	it("should execute runMigrations when adding a new table with indexed columns to an existing database", async () => {
		const config: BetterAuthOptions = {
			database: new DatabaseSync(":memory:"),
			emailAndPassword: {
				enabled: true,
			},
		};

		const initial = await getMigrations(config);
		await initial.runMigrations();

		config.plugins = [
			{
				id: "test-new-table",
				schema: {
					apikey: {
						fields: {
							configId: {
								type: "string",
								required: true,
								index: true,
							},
							referenceId: {
								type: "string",
								required: true,
								index: true,
							},
							key: {
								type: "string",
								required: true,
								index: true,
							},
							createdAt: {
								type: "date",
								required: true,
							},
							updatedAt: {
								type: "date",
								required: true,
							},
						},
					},
				},
			},
		];

		const { runMigrations } = await getMigrations(config);
		await expect(runMigrations()).resolves.not.toThrow();
	});

	/**
	 * @see https://github.com/better-auth/better-auth/issues/9689
	 */
	it("should execute runMigrations when upgrading an existing table with new indexed columns (simulates 1.4.x -> latest)", async () => {
		const db = new DatabaseSync(":memory:");

		const baseConfig: BetterAuthOptions = {
			database: db,
			emailAndPassword: {
				enabled: true,
			},
			plugins: [
				{
					id: "old-apikey",
					schema: {
						apikey: {
							fields: {
								key: {
									type: "string",
									required: true,
								},
								userId: {
									type: "string",
									required: true,
								},
								createdAt: {
									type: "date",
									required: true,
								},
								updatedAt: {
									type: "date",
									required: true,
								},
							},
						},
					},
				},
			],
		};

		const initial = await getMigrations(baseConfig);
		await initial.runMigrations();

		const upgradedConfig: BetterAuthOptions = {
			database: db,
			emailAndPassword: {
				enabled: true,
			},
			plugins: [
				{
					id: "new-apikey",
					schema: {
						apikey: {
							fields: {
								configId: {
									type: "string",
									required: true,
									index: true,
								},
								referenceId: {
									type: "string",
									required: true,
									index: true,
								},
								key: {
									type: "string",
									required: true,
									index: true,
								},
								userId: {
									type: "string",
									required: true,
								},
								createdAt: {
									type: "date",
									required: true,
								},
								updatedAt: {
									type: "date",
									required: true,
								},
							},
						},
					},
				},
			],
		};

		const { runMigrations, toBeAdded } = await getMigrations(upgradedConfig);
		expect(toBeAdded.length).toBeGreaterThan(0);
		const apikeyAdded = toBeAdded.find((t) => t.table === "apikey");
		expect(apikeyAdded).toBeDefined();
		expect(apikeyAdded!.fields).toHaveProperty("configId");
		expect(apikeyAdded!.fields).toHaveProperty("referenceId");

		await expect(runMigrations()).resolves.not.toThrow();
	});

	/**
	 * @see https://github.com/better-auth/better-auth/issues/10306
	 */
	it("should not detect migration changes for SQLite bigint fields on subsequent runs", async () => {
		const config: BetterAuthOptions = {
			database: new DatabaseSync(":memory:"),
			rateLimit: {
				storage: "database",
			},
		};

		const initial = await getMigrations(config);
		await initial.runMigrations();

		const second = await getMigrations(config);
		const { toBeCreated, toBeAdded } = second;

		expect(toBeCreated.length).toBe(0);
		expect(toBeAdded.length).toBe(0);

		const sql = await second.compileMigrations();
		expect(sql).toBe(";");
	});
});
