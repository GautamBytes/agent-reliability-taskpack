const fs=require('node:fs');
const cp=require('node:child_process');
const ts=require('/opt/baseline/node_modules/typescript');
require.extensions['.ts']=function(module,file){ const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;module._compile(code,file); };
const {copySchema}=require('/candidate/docs/lib/copy-schema/index.ts');
const {prismaResolver}=require('/candidate/docs/lib/copy-schema/adapter/prisma.ts');
const parser=require('/opt/baseline/node_modules/.pnpm/@mrleebo+prisma-ast@0.13.1/node_modules/@mrleebo/prisma-ast');
const prismaDir=fs.readdirSync('/opt/baseline/node_modules/.pnpm').find(n=>n.startsWith('prisma@7.4.1_'));
const cli='/opt/baseline/node_modules/.pnpm/'+prismaDir+'/node_modules/prisma/build/index.js';
const fixture={modelName:'deviceCode',fields:[{fieldName:'id',type:'string',required:true},{fieldName:'deviceCode',type:'string',required:true,index:true},{fieldName:'userCode',type:'string',required:true,index:true},{fieldName:'uniqueCode',type:'string',required:true,unique:true,index:true},{fieldName:'label',type:'string',required:false}]};
const records=[];
for(const provider of ['mysql','postgresql','sqlite']){
 const schema=copySchema(fixture,{dialect:prismaResolver({provider}),mode:'create'}).result;
 const parsed=parser.getSchema(schema);fs.writeFileSync('/audit/'+provider+'.prisma',schema);
 const validation=cp.spawnSync(process.execPath,[cli,'format','--schema','/audit/'+provider+'.prisma'],{encoding:'utf8',timeout:20000,env:{...process.env,CHECKPOINT_DISABLE:'1',PRISMA_HIDE_UPDATE_MESSAGE:'1'}});
 fs.writeFileSync('/audit/'+provider+'.format.stdout',validation.stdout||'');fs.writeFileSync('/audit/'+provider+'.format.stderr',validation.stderr||'');
 records.push({provider,generated:schema,old_private_exact_match:schema.includes('@@index([deviceCode]'),parser_accepted:!!parsed.list?.length,prisma_format_exit:validation.status,format_error:validation.error?.message});
}
fs.writeFileSync('/audit/formatting-validation.json',JSON.stringify(records,null,2)+'\n');console.log(JSON.stringify(records.map(({generated,...rest})=>rest)));
