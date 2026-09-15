#!/usr/bin/env node
const base = (process.env.LEGINFO_AI_URL || '').replace(/\/$/, '');
if (!base) {
  console.error('Set LEGINFO_AI_URL to the deployed Worker URL.');
  process.exit(2);
}
const cases = [
  { name: 'exact section', query: 'GOV § 7921.000', expect: '7921.000' },
  { name: 'penal code lookup', query: 'PEN § 187', expect: '187' },
  { name: 'family code lookup', query: 'Family Code 3044', expect: '3044' },
  { name: 'civil code lookup', query: 'Civil Code 1714', expect: '1714' },
  { name: 'concept retrieval', query: 'California public records access', expect: '7921' },
];
let failures = 0;
for (const test of cases) {
  const response = await fetch(`${base}/api/search`, { method: 'POST', headers: {'content-type':'application/json'}, body: JSON.stringify({ query: test.query, limit: 8 }) });
  if (!response.ok) { console.error(`FAIL ${test.name}: HTTP ${response.status}`); failures++; continue; }
  const body = await response.json();
  const haystack = JSON.stringify(body).toLowerCase();
  if (!haystack.includes(test.expect.toLowerCase())) { console.error(`FAIL ${test.name}: expected ${test.expect}`); failures++; }
  else console.log(`PASS ${test.name}`);
}
if (failures) { console.error(`${failures} retrieval regression(s) failed.`); process.exit(1); }
console.log(`All ${cases.length} retrieval regressions passed.`);
