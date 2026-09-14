PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS corpus_versions (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  retrieved_at TEXT NOT NULL,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS law_sections (
  uid TEXT PRIMARY KEY,
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
  corpus_version_id TEXT REFERENCES corpus_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_law_sections_code ON law_sections(code);
CREATE INDEX IF NOT EXISTS idx_law_sections_code_section ON law_sections(code, section);

CREATE TABLE IF NOT EXISTS law_toc (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  kind TEXT NOT NULL,
  number TEXT,
  title TEXT,
  range_start TEXT,
  range_end TEXT,
  path TEXT,
  ordinal INTEGER,
  corpus_version_id TEXT REFERENCES corpus_versions(id)
);

CREATE INDEX IF NOT EXISTS idx_law_toc_code ON law_toc(code);

CREATE TABLE IF NOT EXISTS section_relationships (
  source_uid TEXT NOT NULL,
  target_uid TEXT,
  relationship TEXT NOT NULL,
  reference_text TEXT,
  confidence REAL NOT NULL DEFAULT 1.0,
  PRIMARY KEY (source_uid, target_uid, relationship, reference_text)
);

CREATE INDEX IF NOT EXISTS idx_section_relationships_source
  ON section_relationships(source_uid, relationship);
CREATE INDEX IF NOT EXISTS idx_section_relationships_target
  ON section_relationships(target_uid, relationship);

CREATE TABLE IF NOT EXISTS derived_ai_artifacts (
  id TEXT PRIMARY KEY,
  artifact_type TEXT NOT NULL,
  source_uid TEXT,
  source_version_id TEXT,
  model TEXT,
  created_at TEXT NOT NULL,
  content_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_derived_ai_artifacts_source
  ON derived_ai_artifacts(source_uid, artifact_type);

CREATE VIRTUAL TABLE IF NOT EXISTS law_sections_fts USING fts5(
  uid UNINDEXED,
  code UNINDEXED,
  section UNINDEXED,
  citation,
  text,
  history,
  content='law_sections',
  content_rowid='rowid',
  tokenize='porter unicode61'
);
