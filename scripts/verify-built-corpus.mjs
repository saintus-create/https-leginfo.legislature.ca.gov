#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { createReadStream } from 'node:fs';
import { readdir, readFile } from 'node:fs/promises';
import { createInterface } from 'node:readline';
import { join } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const sourceDir = join(root, 'data', 'law');
const publicLaw = join(root, 'public', 'data', 'law');
const indexPath = join(root, 'public', 'data', 'research-index.json');
const manifestPath = join(publicLaw, 'manifest.json');
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
const index = JSON.parse(await readFile(indexPath, 'utf8'));
const expectedCodes = Object.keys(manifest.codes || {}).sort();
if (!expectedCodes.length) throw new Error('Built corpus manifest is empty.');
if (!index.codes || !index.locations) throw new Error('Research index is missing codes or locations.');

async function sha256(path) {
  return await new Promise((resolve, reject) => {
    const hash = createHash('sha256');
    const stream = createReadStream(path);
    stream.on('data', (chunk) => hash.update(chunk));
    stream.on('error', reject);
    stream.on('end', () => resolve(hash.digest('hex')));
  });
}

const sourceFiles = (await readdir(sourceDir)).filter((n) => n.endsWith('.jsonl.gz')).sort();
if (sourceFiles.length !== expectedCodes.length) throw new Error(`Source/deployed code count mismatch: ${sourceFiles.length} vs ${expectedCodes.length}.`);
for (const code of expectedCodes) {
  const entry = manifest.source?.[code];
  if (!entry) throw new Error(`${code}: missing source checksum.`);
  const actual = await sha256(join(sourceDir, entry.file));
  if (actual !== entry.sha256) throw new Error(`${code}: source SHA-256 mismatch.`);
}

const actualParts = new Set((await readdir(publicLaw)).filter((n) => /\.part-\d+$/.test(n)));
const seenUids = new Set();
const partUids = new Map();
let totalSections = 0;

for (const code of expectedCodes) {
  const parts = manifest.codes[code];
  if (!Array.isArray(parts) || !parts.length) throw new Error(`${code}: manifest has no corpus parts.`);
  let count = 0;
  for (const part of parts) {
    if (!actualParts.has(part)) throw new Error(`${code}: manifest references missing part ${part}.`);
    const path = join(publicLaw, part);
    const hash = createHash('sha256');
    const lines = createInterface({ input: createReadStream(path), crlfDelay: Infinity });
    const uids = [];
    for await (const line of lines) {
      if (!line.trim()) continue;
      hash.update(line + '\n');
      let rec;
      try { rec = JSON.parse(line); } catch (error) { throw new Error(`${part}: invalid JSON: ${error.message}`); }
      if (rec.kind !== 'section') continue;
      count += 1;
      totalSections += 1;
      if (typeof rec.uid !== 'string' || !rec.uid.trim()) throw new Error(`${part}: section missing uid.`);
      if (seenUids.has(rec.uid)) throw new Error(`Duplicate section uid: ${rec.uid}`);
      seenUids.add(rec.uid);
      uids.push(rec.uid);
      if (typeof rec.citation !== 'string' || !rec.citation.trim()) throw new Error(`${rec.uid}: missing citation.`);
      if (typeof rec.text !== 'string' || !rec.text.trim()) throw new Error(`${rec.uid}: missing statutory text.`);
    }
    partUids.set(part, uids);
    const expectedHash = manifest._parts?.[part]?.sha256;
    const actualHash = hash.digest('hex');
    if (!expectedHash || expectedHash !== actualHash) throw new Error(`${part}: deployed SHA-256 mismatch.`);
  }
  const expected = Number(index.codes[code]?.sectionCount);
  if (!Number.isInteger(expected) || expected !== count) throw new Error(`${code}: section count mismatch; index=${expected}, built=${count}.`);
}

for (const [uid, part] of Object.entries(index.locations)) {
  if (!seenUids.has(uid)) throw new Error(`Research-index citation points to nonexistent section: ${uid}`);
  if (!partUids.has(part) || !partUids.get(part).includes(uid)) throw new Error(`Research-index location is invalid for ${uid}: ${part}`);
}
for (const [code, meta] of Object.entries(index.codes)) {
  if (!manifest.codes[code]) throw new Error(`Research index contains unknown code ${code}.`);
  for (const key of ['longestSentenceByWords', 'longestSentenceByChars']) {
    const section = meta[key]?.section;
    const uid = meta[key]?.uid || (section ? `${code}:${section}` : undefined);
    if (uid && !seenUids.has(uid)) throw new Error(`${code}: ${key} citation does not resolve.`);
  }
}

console.log(`Built corpus integrity verified: ${expectedCodes.length} codes, ${totalSections.toLocaleString()} sections, ${seenUids.size.toLocaleString()} unique citations, source and deployed SHA-256 checksums valid.`);
