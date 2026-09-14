#!/usr/bin/env node
import { createReadStream } from 'node:fs';
import { readdir } from 'node:fs/promises';
import { createGunzip } from 'node:zlib';
import { createInterface } from 'node:readline';
import { join } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const lawDir = join(root, 'data', 'law');
const files = (await readdir(lawDir)).filter((name) => name.endsWith('.jsonl.gz')).sort();

if (!files.length) throw new Error('No compressed legislative corpus files found.');

let total = 0;
let sections = 0;
const seenUids = new Set();

for (const name of files) {
  const code = name.replace(/\.jsonl\.gz$/, '');
  let count = 0;
  let fileSections = 0;

  const input = createReadStream(join(lawDir, name));
  const gunzip = createGunzip();
  const lines = createInterface({ input: input.pipe(gunzip), crlfDelay: Infinity });

  try {
    for await (const line of lines) {
      if (!line.trim()) continue;
      let record;
      try {
        record = JSON.parse(line);
      } catch (error) {
        throw new Error(`${name}: invalid JSON at record ${count + 1}: ${error.message}`);
      }

      if (!record || typeof record !== 'object' || Array.isArray(record)) {
        throw new Error(`${name}: record ${count + 1} is not a JSON object.`);
      }

      count += 1;
      total += 1;

      if (record.kind === 'section') {
        fileSections += 1;
        sections += 1;
        if (typeof record.uid !== 'string' || !record.uid.trim()) {
          throw new Error(`${name}: section record ${count} is missing uid.`);
        }
        if (seenUids.has(record.uid)) {
          throw new Error(`Duplicate section uid: ${record.uid}`);
        }
        seenUids.add(record.uid);
      }

      if (record.code !== undefined && record.code !== code) {
        throw new Error(`${name}: record ${count} declares code ${JSON.stringify(record.code)} instead of ${code}.`);
      }
    }
  } finally {
    lines.close();
  }

  if (count === 0) throw new Error(`${name}: corpus file is empty.`);
  console.log(`${code}: ${count.toLocaleString()} records, ${fileSections.toLocaleString()} sections`);
}

console.log(`Validated ${files.length} code files, ${total.toLocaleString()} records, ${sections.toLocaleString()} sections.`);
