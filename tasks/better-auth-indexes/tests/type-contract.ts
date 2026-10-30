import { copySchema } from "../docs/lib/copy-schema";
import type { DBSchema } from "../docs/lib/copy-schema/types";
const schema = {
 modelName: "deviceCode",
 fields: [{fieldName:"id",type:"string",required:true},{fieldName:"deviceCode",type:"string",index:true}]
} satisfies DBSchema;
copySchema(schema,{dialect:"sqlite",mode:"create"});
