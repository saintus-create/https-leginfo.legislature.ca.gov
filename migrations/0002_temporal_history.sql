PRAGMA foreign_keys = ON;

-- Immutable snapshots of a code corpus. A corpus version identifies the source
-- snapshot, while section versions below preserve the text that existed in it.
CREATE TABLE IF NOT EXISTS law_section_versions (
  uid TEXT NOT NULL,
  corpus_version_id TEXT NOT NULL REFERENCES corpus_versions(id),
  code TEXT NOT NULL,
  section TEXT NOT NULL,
  citation TEXT,
  title TEXT,
  text TEXT,
  history TEXT,
  repealed INTEGER NOT NULL DEFAULT 0,
  division TEXT,
  part TEXT,
  title_path TEXT,
  chapter TEXT,
  article TEXT,
  path TEXT,
  char_count INTEGER,
  valid_from TEXT,
  valid_to TEXT,
  version_status TEXT NOT NULL DEFAULT 'effective',
  source_key TEXT,
  source_url TEXT,
  content_hash TEXT,
  PRIMARY KEY (uid, corpus_version_id)
);

CREATE INDEX IF NOT EXISTS idx_section_versions_uid_dates
  ON law_section_versions(uid, valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_section_versions_code_section
  ON law_section_versions(code, section, valid_from);
CREATE INDEX IF NOT EXISTS idx_section_versions_hash
  ON law_section_versions(content_hash);

-- Legislative events are kept separately from section text because one bill,
-- chapter, or amendment can affect many sections and a section can have many events.
CREATE TABLE IF NOT EXISTS legislative_history_events (
  id TEXT PRIMARY KEY,
  uid TEXT NOT NULL,
  version_id TEXT,
  event_type TEXT NOT NULL,
  effective_date TEXT,
  enacted_date TEXT,
  session TEXT,
  bill_id TEXT,
  chapter TEXT,
  description TEXT,
  source_key TEXT,
  source_url TEXT,
  source_hash TEXT,
  sequence INTEGER,
  FOREIGN KEY (uid, version_id) REFERENCES law_section_versions(uid, corpus_version_id)
);

CREATE INDEX IF NOT EXISTS idx_history_events_uid_date
  ON legislative_history_events(uid, effective_date, enacted_date);
CREATE INDEX IF NOT EXISTS idx_history_events_bill
  ON legislative_history_events(bill_id);
CREATE INDEX IF NOT EXISTS idx_history_events_version
  ON legislative_history_events(version_id);

-- Bill/chapter-level source metadata lets the retriever explain where a history
-- event came from without treating generated AI artifacts as primary evidence.
CREATE TABLE IF NOT EXISTS legislative_sources (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  external_id TEXT,
  title TEXT,
  published_at TEXT,
  source_key TEXT NOT NULL,
  source_url TEXT,
  content_hash TEXT,
  metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_legislative_sources_external
  ON legislative_sources(source_type, external_id);

-- Optional links between a section version and a source record such as a bill,
-- chapter, enrolled bill, or official historical document.
CREATE TABLE IF NOT EXISTS section_version_sources (
  uid TEXT NOT NULL,
  corpus_version_id TEXT NOT NULL,
  source_id TEXT NOT NULL REFERENCES legislative_sources(id),
  role TEXT NOT NULL,
  PRIMARY KEY (uid, corpus_version_id, source_id, role),
  FOREIGN KEY (uid, corpus_version_id) REFERENCES law_section_versions(uid, corpus_version_id)
);

CREATE INDEX IF NOT EXISTS idx_section_version_sources_source
  ON section_version_sources(source_id);
