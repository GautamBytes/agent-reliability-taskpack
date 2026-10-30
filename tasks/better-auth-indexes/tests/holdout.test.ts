import { DatabaseSync } from "node:sqlite";
import { createRequire } from "node:module";
import { is } from "drizzle-orm";
import * as mysqlCore from "drizzle-orm/mysql-core";
import * as pgCore from "drizzle-orm/pg-core";
import * as sqliteCore from "drizzle-orm/sqlite-core";
import ts from "typescript";
import type { BetterAuthOptions } from "@better-auth/core";
import { describe, expect, it } from "vitest";
import { copySchema } from "../docs/lib/copy-schema";
import { drizzleResolver } from "../docs/lib/copy-schema/adapter/drizzle";
import { prismaResolver } from "../docs/lib/copy-schema/adapter/prisma";
import type { DBSchema, DefaultDialects } from "../docs/lib/copy-schema/types";
import { getMigrations } from "../packages/better-auth/src/db/get-migration";
import { deviceAuthorization, deviceAuthorizationOptionsSchema } from "../packages/better-auth/src/plugins/device-authorization";
import { getTestInstance } from "../packages/better-auth/src/test-utils/test-instance";

const dialects: DefaultDialects[] = ["sqlite", "postgresql", "mysql", "mssql"];
function fixture(modelName = "deviceCode"): DBSchema {
 return {modelName, fields: [
  {fieldName:"id",type:"string",required:true},
  {fieldName:"deviceCode",type:"string",required:true,index:true},
  {fieldName:"userCode",type:"string",required:true,index:true},
  {fieldName:"uniqueCode",type:"string",required:true,unique:true,index:true},
  {fieldName:"label",type:"string",required:false},
 ]};
}
function sqlIndexNames(sql: string): string[] {
 const result=[];
 for (const match of sql.matchAll(/CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?["`\[]([^"`\]]+)["`\]]/gi)) result.push(match[1]);
 return result;
}
function nonUniqueIndexFields(db: DatabaseSync, table: string) {
 const indexes=db.prepare(`PRAGMA index_list("${table}")`).all();
 return indexes.filter(row=>row.unique===0).map(row=>{
  if(typeof row.name!=="string") throw new Error("SQLite returned non-string index name");
  return db.prepare(`PRAGMA index_info("${row.name.replaceAll('"','""')}")`).all().map(field=>field.name);
 });
}

function drizzleMetadata(source: string, provider: "mysql" | "pg" | "sqlite") {
 const module: { exports: Record<string, unknown> } = { exports: {} };
 const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const evaluate=new Function("require","exports","module",compiled);
 evaluate(createRequire(import.meta.url),module.exports,module);
 const table=module.exports.deviceCode;
 const config=provider==="mysql"&&is(table,mysqlCore.MySqlTable)?mysqlCore.getTableConfig(table)
  :provider==="pg"&&is(table,pgCore.PgTable)?pgCore.getTableConfig(table)
  :provider==="sqlite"&&is(table,sqliteCore.SQLiteTable)?sqliteCore.getTableConfig(table)
  :undefined;
 if(!config) throw new Error("Generated schema did not export the requested Drizzle table");
 const fields=config.indexes.filter(index=>!index.config.unique).map(index=>index.config.columns.map(column=>{
  if(!("name" in column)||typeof column.name!=="string") throw new Error("Index must reference a generated field");
  return column.name;
 }));
 const indexedTypes=config.columns.filter(column=>["device_code","user_code"].includes(column.name)).map(column=>column.getSQLType());
 return {fields,indexedTypes};
}

describe("holdout portable lookup indexes",()=>{
 it("creates non-unique lookup indexes through the real plugin migration",async()=>{
  const db=new DatabaseSync(":memory:");
  try{
   await(await getMigrations({database:db,plugins:[deviceAuthorization()]})).runMigrations();
   expect(nonUniqueIndexFields(db,"deviceCode")).toEqual(expect.arrayContaining([["deviceCode"],["userCode"]]));
  }finally{db.close();}
 });
 it.each(dialects)("emits exactly two non-unique indexes in %s",dialect=>{
  const result=copySchema(fixture(),{dialect,mode:"create"}).result;
  expect(sqlIndexNames(result)).toHaveLength(2);
  expect(result).not.toContain("uniqueCode_idx");
 });
 it.each(dialects)("emits non-unique indexes in alter mode for %s",dialect=>{
  const result=copySchema(fixture(),{dialect,mode:"alter"}).result;
  expect(sqlIndexNames(result)).toHaveLength(2);
  expect(result).not.toContain("uniqueCode_idx");
 });
 it("executes generated SQLite DDL twice and still permits repeated indexed values",()=>{
  const db=new DatabaseSync(":memory:");
  try{
   const sql=copySchema(fixture(),{dialect:"sqlite",mode:"create"}).result;
   db.exec(sql); db.exec(sql);
   expect(nonUniqueIndexFields(db,"deviceCode")).toEqual(expect.arrayContaining([["deviceCode"],["userCode"]]));
   db.exec(`INSERT INTO "deviceCode"(id,deviceCode,userCode,uniqueCode) VALUES ('a','same','same','first'),('b','same','same','second')`);
   expect(db.prepare('SELECT COUNT(*) AS count FROM "deviceCode"').get()?.count).toBe(2);
   expect(()=>db.exec(`INSERT INTO "deviceCode"(id,deviceCode,userCode,uniqueCode) VALUES ('c','different','different','first')`)).toThrow();
   expect(db.prepare('SELECT COUNT(*) AS count FROM "deviceCode"').get()?.count).toBe(2);
  }finally{db.close();}
 });
 it("upgrades existing populated SQLite device storage and has no second migration",async()=>{
  const db=new DatabaseSync(":memory:");
  try{
   const plugin=deviceAuthorization();
   const old:BetterAuthOptions={database:db,plugins:[{id:"legacy-device",schema:{deviceCode:{...plugin.schema.deviceCode,indexes:[]}}}]};
   await (await getMigrations(old)).runMigrations();
   db.exec(`INSERT INTO deviceCode(id,deviceCode,userCode,expiresAt,status,pollingInterval,clientId) VALUES ('fixture','d','u',0,'pending',5000,'client')`);
   const next={database:db,plugins:[plugin]};
   await (await getMigrations(next)).runMigrations();
   expect(nonUniqueIndexFields(db,"deviceCode")).toEqual(expect.arrayContaining([["deviceCode"],["userCode"]]));
   expect(db.prepare("SELECT COUNT(*) AS count FROM deviceCode").get()?.count).toBe(1);
   expect((await getMigrations(next)).toBeAdded).toEqual([]);
   expect(await(await getMigrations(next)).compileMigrations()).toBe(";");
  }finally{db.close();}
 });
 it("keeps filtered fields out of the generated index set",()=>{
  const schema=fixture();
  schema.fields.push({fieldName:"conditional",type:"string",index:true,condition:"feature"});
  const absent=copySchema(schema,{dialect:"sqlite",mode:"create",conditions:{feature:false}}).result;
  const present=copySchema(schema,{dialect:"sqlite",mode:"create",conditions:{feature:true}}).result;
  expect(sqlIndexNames(absent)).toHaveLength(2);
  expect(sqlIndexNames(present)).toHaveLength(3);
 });
 it.each(["mysql","mssql"] satisfies DefaultDialects[])("uses bounded string columns in %s",dialect=>{
  const result=copySchema(fixture(),{dialect,mode:"create"}).result;
  for(const field of ["deviceCode","userCode"]){
   if(dialect === "mysql"){
    expect(result).toMatch(new RegExp("`"+field+"`\\s+varchar\\(191\\)","i"));
   }else{
    const match=result.match(new RegExp("\\["+field+"\\]\\s+(?:varchar|nvarchar)\\((\\d+)\\)","i"));
    expect(match).not.toBeNull();
    const length=Number(match?.[1]);
    expect(length).toBeGreaterThan(0);
    expect(length).toBeLessThanOrEqual(255);
   }
  }
 });
 it("guards MySQL index creation with table and index existence predicates",()=>{
  const result=copySchema(fixture("team's_codes"),{dialect:"mysql",mode:"create"}).result;
  expect(result).toMatch(/information_schema\.tables/i);
  expect(result).toMatch(/information_schema\.statistics/i);
  expect(result).toMatch(/table_name\s*=\s*'team''s_codes'/i);
  expect(result).toMatch(/(?:IF\s*\(|\bIF\s+|\bCASE\s+)/i);
 });
 it("guards SQL Server index creation for the target object",()=>{
  const result=copySchema(fixture("team's_codes"),{dialect:"mssql",mode:"create"}).result;
  expect(result).toMatch(/sys\.indexes/i);
  expect(result).toMatch(/NOT\s+EXISTS/i);
  expect(result).toMatch(/OBJECT_ID\s*\(\s*N?'(?:\[)?team''s_codes(?:\])?'(?:\s*,\s*N?'U')?\s*\)/i);
 });
 it.each(["mysql","postgresql","sqlite"])("preserves index semantics in Prisma %s output",provider=>{
  if(provider!=="mysql"&&provider!=="postgresql"&&provider!=="sqlite") throw new Error("bad fixture");
  const result=copySchema(fixture(),{dialect:prismaResolver({provider}),mode:"create"}).result;
  expect(result.match(/@@index\s*\(/g)).toHaveLength(2);
  expect(result).toMatch(/@@index\s*\(\s*(?:fields\s*:\s*)?\[\s*deviceCode\s*\]/);
  expect(result).toMatch(/@@index\s*\(\s*(?:fields\s*:\s*)?\[\s*userCode\s*\]/);
  expect(result).not.toMatch(/@@index\s*\(\s*(?:fields\s*:\s*)?\[\s*uniqueCode\s*\]/);
 });
 it.each(["mysql","pg","sqlite"])("preserves index semantics in Drizzle %s output",provider=>{
  if(provider!=="mysql"&&provider!=="pg"&&provider!=="sqlite") throw new Error("bad fixture");
  const result=copySchema(fixture(),{dialect:drizzleResolver({provider}),mode:"create"}).result;
  const metadata=drizzleMetadata(result,provider);
  expect(metadata.fields).toHaveLength(2);
  expect(metadata.fields).toEqual(expect.arrayContaining([["device_code"],["user_code"]]));
  expect(metadata.fields.flat()).not.toContain("unique_code");
  if(provider==="mysql") expect(metadata.indexedTypes.map(type=>type.toLowerCase())).toEqual(["varchar(191)","varchar(191)"]);
 });
 it.each(["table".repeat(20),"数据库".repeat(20),"🦋".repeat(45)])("keeps long name family %s portable and distinct",name=>{
  const schema=fixture(name);
  schema.fields[1].fieldName="first_shared_prefix_".repeat(7)+"A";
  schema.fields[2].fieldName="first_shared_prefix_".repeat(7)+"B";
  const outputs=dialects.map(dialect=>sqlIndexNames(copySchema(schema,{dialect,mode:"create"}).result));
  for(const names of outputs){
   expect(names).toHaveLength(2);
   expect(new Set(names).size).toBe(2);
   for(const value of names){expect(new TextEncoder().encode(value).length).toBeLessThanOrEqual(63);expect(value).not.toContain("\uFFFD");}
  }
  for(const names of outputs) expect(names).toEqual(outputs[0]);
 });
});

describe("holdout generated-code boundary",()=>{
 it.each(["deviceCodeLength","userCodeLength"])("rejects oversized configured %s",key=>{
  expect(()=>deviceAuthorizationOptionsSchema.parse({[key]:192})).toThrow();
  expect(()=>deviceAuthorizationOptionsSchema.parse({[key]:191})).not.toThrow();
 });
 it.each(["device","user"])("rejects oversized custom %s code before persistence",async label=>{
  const options=deviceAuthorizationOptionsSchema.parse(label==="device"?{generateDeviceCode:()=>"🦋".repeat(192)}:{generateUserCode:()=>"x".repeat(192)});
  const {auth}=await getTestInstance({plugins:[deviceAuthorization(options)]});
  await expect(auth.api.deviceCode({body:{client_id:"test-client"}})).rejects.toMatchObject({body:{error:"invalid_request"}});
  expect(await(await auth.$context).adapter.findMany({model:"deviceCode"})).toEqual([]);
 });
 it.each(["device","user"])("rejects non-string custom %s code before persistence",async label=>{
  const options=deviceAuthorizationOptionsSchema.parse(label==="device"?{generateDeviceCode:()=>42}:{generateUserCode:()=>({value:"code"})});
  const {auth}=await getTestInstance({plugins:[deviceAuthorization(options)]});
  await expect(auth.api.deviceCode({body:{client_id:"test-client"}})).rejects.toMatchObject({body:{error:"invalid_request"}});
  expect(await(await auth.$context).adapter.findMany({model:"deviceCode"})).toEqual([]);
 });
 it("accepts exactly 191 Unicode code points rather than counting UTF-16 units",async()=>{
  const value="🦋".repeat(191);
  const {auth}=await getTestInstance({plugins:[deviceAuthorization({generateDeviceCode:async()=>value,generateUserCode:()=>"u".repeat(191)})]});
  const result=await auth.api.deviceCode({body:{client_id:"test-client"}});
  expect(result.device_code).toBe(value);
  expect(result.user_code).toHaveLength(191);
 });
});
