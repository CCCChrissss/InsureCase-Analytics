PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS cases (
  case_id TEXT PRIMARY KEY,
  case_number TEXT NOT NULL UNIQUE,
  roc_year INTEGER NOT NULL,
  decision_date TEXT,
  decision_category TEXT,
  decision_result TEXT,
  industry TEXT,
  industry_subcategory TEXT,
  dispute_type TEXT,
  source_pdf_url TEXT,
  case_directory TEXT,
  pdf_path TEXT,
  raw_text_path TEXT,
  normalized_text_path TEXT,
  metadata_path TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_texts (
  case_id TEXT PRIMARY KEY,
  raw_text TEXT,
  normalized_text TEXT,
  raw_text_chars INTEGER,
  normalized_text_chars INTEGER,
  page_count INTEGER,
  extraction_method TEXT,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_summaries (
  case_id TEXT PRIMARY KEY,
  holding TEXT,
  applicant_claim TEXT,
  reasoning TEXT,
  summary_method TEXT,
  created_at TEXT,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS case_chunks (
  chunk_id TEXT PRIMARY KEY,
  case_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  section_hint TEXT,
  chunk_text TEXT NOT NULL,
  char_start INTEGER NOT NULL,
  char_end INTEGER NOT NULL,
  chunk_chars INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
  UNIQUE(case_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
  chunk_id TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  embedding_dims INTEGER NOT NULL,
  embedding BLOB NOT NULL,
  embedding_norm REAL NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(chunk_id) REFERENCES case_chunks(chunk_id) ON DELETE CASCADE,
  PRIMARY KEY(chunk_id, embedding_model)
);

CREATE VIRTUAL TABLE IF NOT EXISTS case_search USING fts5(
  case_id UNINDEXED,
  case_number,
  dispute_type,
  normalized_text
);

CREATE INDEX IF NOT EXISTS idx_cases_roc_year ON cases(roc_year);
CREATE INDEX IF NOT EXISTS idx_cases_decision_date ON cases(decision_date);
CREATE INDEX IF NOT EXISTS idx_cases_dispute_type ON cases(dispute_type);
CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);
CREATE INDEX IF NOT EXISTS idx_case_chunks_case_id ON case_chunks(case_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(embedding_model);
