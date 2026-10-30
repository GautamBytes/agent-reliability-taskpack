import { defineConfig } from 'vitest/config';
import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
const alias = [];
for (const directory of readdirSync(resolve('packages'))) {
 let metadata;
 try { metadata = JSON.parse(readFileSync(resolve('packages', directory, 'package.json'), 'utf8')); } catch { continue; }
 for (const [key, options] of Object.entries(metadata.exports ?? {})) {
  const source = options?.['dev-source'];
  if (typeof source !== 'string') continue;
  const specifier = metadata.name + (key === '.' ? '' : key.slice(1));
  const pattern = specifier.split('*').map(value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('(.*)');
  alias.push({find: new RegExp('^' + pattern + '$'), replacement: resolve('packages', directory, source).replace('*', '$1')});
 }
}
export default defineConfig({
 resolve: { alias },
 test: { include: ['packages/better-auth/src/plugins/device-authorization/device-authorization.test.ts', 'packages/better-auth/src/db/get-migration-schema.test.ts'], maxWorkers: 2, testTimeout: 10000, reporters: ['default', 'json'], outputFile: '/private/tmp/betterauth-v2-work/initial-results.json' }
});
