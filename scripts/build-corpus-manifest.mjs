#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { readdir, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const sourceDir = join(root, 'data', 'law');
const publicDir = join(root, 'public', 'data', 'law');
const sourceFiles = (await readdir(sourceDir)).filter((n) => n.endsWith('.jsonl.gz')).sort();
const partFiles = (await readdir(publicDir)).filter((n) => /\.part-\d+$/.test(n)).sort();
const manifest = { version: 2, generatedAt: new Date().toISOString(), source: {}, codes: {}, _parts: {} };

async function sha256(path) {
  return await new Promise((resolve, reject) => {
    const hash = createHash('sha256');
    const stream = createReadStream(path);
    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('error', reject);
    stream.on('end', () => resolve(hash.digest('hex')));
  });
}

for (const file of sourceFiles) {
  const code = file.replace(/\.jsonl\.gz$/, '').toUpperCase();
  const st = await stat(join(sourceDir, file));
  manifest.source[code] = { file, bytes: st.size, sha256: await sha256(join(sourceDir, file)) };
  manifest.codes[code] = [];
}
for (const part of partFiles) {
  const code = part.split('.part-')[0].toUpperCase();
  if (!manifest.codes[code]) throw new Error(`Built part has no source code: ${part}`);
  const st = await stat(join(publicDir, part));
  manifest.codes[code].push(part);
  manifest._parts[part] = { bytes: st.size, sha256: await sha256(join(publicDir, part)) };
}
for (const code of Object.keys(manifest.codes)) {
  if (!manifest.codes[code].length) throw new Error(`${code}: no built corpus parts.`);
}
await writeFile(join(publicDir, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n', 'utf8');
console.log(`Corpus manifest written: ${sourceFiles.length} source files, ${partFiles.length} deployed parts.`);
