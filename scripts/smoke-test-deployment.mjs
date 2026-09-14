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
const terms = ['government', '6250'];
const candidates = new Set();
for (const term of terms) for (const uid of index.terms?.[term] || []) candidates.add(String(uid).split(':')[0]);
candidates.add('GOV');

let found = null;
for (const code of candidates) {
  for (const part of manifest.codes[code] || []) {
    const text = await (await get(`/data/law/${part}`)).text();
    for (const line of text.split('\n')) {
      if (!line.trim()) continue;
      const rec = JSON.parse(line);
      if (rec.kind === 'section' && String(rec.code).toUpperCase() === 'GOV' && String(rec.section) === '6250' && typeof rec.citation === 'string' && rec.text?.trim()) {
        found = rec;
        break;
      }
    }
    if (found) break;
  }
  if (found) break;
}
if (!found) throw new Error(`Deployed query failed: ${query} returned no verified statutory section.`);

const expectedSource = 'https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=6250.';
const sourceUrl = found.url || found.link || found.source_url || '';
if (sourceUrl && sourceUrl !== expectedSource) throw new Error(`Unexpected statutory source URL for ${found.uid}: ${sourceUrl}`);
console.log(`DEPLOYMENT SMOKE TEST PASSED: "${query}" retrieved ${found.uid} (${found.citation}) with statutory text from the deployed corpus.`);
