PRAGMA foreign_keys = ON;

-- Immutable temporal records. law_sections remains the current/search projection.
CREATE TABLE IF NOT EXISTS law_section_versions (
  uid TEXT NOT NULL,
  corpus_version_id TEXT NOT NULL REFERENCES corpus_versions(id),
  code TEXT NOT NULL,
  section TEXT NOT NULL,
  citation TEXT,
  ordinal INTEGER,
  text TEXT,
  history TEXT,
  repealed INTEGER NOT NULL DEFAULT 0,
  division TEXT,
  part TEXT,
  title TEXT,
  chapter TEXT,
  article TEXT,
  path TEXT,
  char_count INTEGER,
  content_hash TEXT,
  source_object_key TEXT,
  effective_from TEXT,
  effective_to TEXT,
  PRIMARY KEY (uid, corpus_version_id)
);

CREATE INDEX IF NOT EXISTS idx_law_section_versions_uid
  ON law_section_versions(uid);
CREATE INDEX IF NOT EXISTS idx_law_section_versions_code_section
  ON law_section_versions(code, section);
CREATE INDEX IF NOT EXISTS idx_law_section_versions_effective
  ON law_section_versions(uid, effective_from, effective_to);

-- Legal events explain why a provision changed. Multiple source records can support one event.
CREATE TABLE IF NOT EXISTS legislative_history_events (
  id TEXT PRIMARY KEY,
  uid TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_date TEXT,
  effective_date TEXT,
  session TEXT,
  bill_id TEXT,
  chapter TEXT,
  description TEXT,
  source_object_key TEXT,
  source_url TEXT,
  source_hash TEXT,
  corpus_version_id TEXT REFERENCES corpus_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_history_events_uid_date
  ON legislative_history_events(uid, event_date);
CREATE INDEX IF NOT EXISTS idx_history_events_bill
  ON legislative_history_events(bill_id);

CREATE TABLE IF NOT EXISTS legislative_history_sources (
  id TEXT PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES legislative_history_events(id),
  source_type TEXT NOT NULL,
  citation TEXT,
  title TEXT,
  event_date TEXT,
  object_key TEXT NOT NULL,
  source_url TEXT,
  content_hash TEXT,
  metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_sources_event
  ON legislative_history_sources(event_id);

-- Explicit version-to-version relationships support temporal comparison and provenance.
CREATE TABLE IF NOT EXISTS section_version_changes (
  uid TEXT NOT NULL,
  from_version_id TEXT NOT NULL REFERENCES corpus_versions(id),
  to_version_id TEXT NOT NULL REFERENCES corpus_versions(id),
  change_type TEXT NOT NULL,
  previous_hash TEXT,
  current_hash TEXT,
  diff_object_key TEXT,
  summary TEXT,
  PRIMARY KEY (uid, from_version_id, to_version_id)
);

CREATE INDEX IF NOT EXISTS idx_section_version_changes_uid
  ON section_version_changes(uid, to_version_id);

-- R2 is the durable source for full historical documents/diffs; D1 stores searchable metadata.
-- Recommended object layout:
--   corpus/{version}/law/{code}/{section}.json
--   history/{code}/{section}/{event-id}/source.json
--   history/{code}/{section}/{event-id}/diff.json
--   history/{code}/{section}/{event-id}/sources/{source-id}.json
--   history/bills/{bill-id}/{source-id}.json
