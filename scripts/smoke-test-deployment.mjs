#!/usr/bin/env node
const site = (process.argv[2] || 'https://saintus-create.github.io/https-leginfo.legislature.ca.gov/').replace(/\/$/, '');
const get = async (path) => {
  const r = await fetch(`${site}${path}`);
  if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
  return r;
};

const manifest = await (await get('/data/law/manifest.json')).json();
if (!manifest.codes || !manifest._parts) throw new Error('Deployed manifest is missing integrity metadata.');
const index = await (await get('/data/research-index.json')).json();

const query = 'Government Code 6250';
const expectedUid = 'GOV:6250';
const part = index.locations?.[expectedUid];
if (!part || !manifest.codes.GOV?.includes(part)) throw new Error(`Deployed research index cannot locate ${expectedUid}.`);

const terms = query.toLowerCase().match(/[a-z0-9][a-z0-9._-]{2,}/g) || [];
const text = await (await get(`/data/law/${part}`)).text();
let found = null;
for (const line of text.split('\n')) {
  if (!line.trim()) continue;
  const rec = JSON.parse(line);
  if (rec.kind !== 'section') continue;
  const hay = `${rec.title || ''} ${rec.text || ''}`.toLowerCase();
  const hits = terms.filter((term) => hay.includes(term)).length;
  if (rec.uid === expectedUid && hits >= 2 && typeof rec.citation === 'string' && rec.citation.trim() && typeof rec.text === 'string' && rec.text.trim()) {
    found = rec;
    break;
  }
}
if (!found) throw new Error(`Deployed query failed: ${query} did not retrieve verified statutory section ${expectedUid}.`);
console.log(`DEPLOYMENT SMOKE TEST PASSED: "${query}" retrieved ${found.uid} (${found.citation}) with ${found.text.length.toLocaleString()} characters of statutory text from the deployed corpus.`);
