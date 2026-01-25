export type Lot = {
  duration?: { value: string; unit: string } | null;
  identifier: string;
  title: string;
  description: string;
  deadline: string | null;
  value: string | null;
  currency: string;
  documents: string[];
  requirements: string[];
  cpv: string[];
};
export type Comparison = {
  before: string;
  after: string;
  fields: { field: string; before: unknown; after: unknown }[];
};
export type Notice = {
  id: number;
  publication_id: string;
  title: string;
  description: string;
  buyer: string;
  country: string;
  published: string;
  kind: string;
  status: string;
  deadline: string | null;
  language: string;
  quality: string;
  source_url: string;
  cpv: string[];
  changed: boolean;
  warnings: string[];
  lots?: Lot[];
  versions?: {
    publication_id: string;
    published: string;
    kind: string;
    title: string;
    checksum: string;
    quality: string;
  }[];
  changes?: string[];
  previous?: string[];
  documents?: string[];
  retrieved_at?: string;
  checksum?: string;
  comparison?: Comparison | null;
  excerpts?: { text: string; source: string }[];
};
export type Results = {
  items: Notice[];
  total: number;
  backend: string;
  warnings: string[];
  candidate_limit?: number;
};
export type ImportRun = {
  id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  seen: number;
  created: number;
  unchanged: number;
  error_count: number;
  truncated: boolean;
  source_total: number | null;
};
export type Collection = {
  notices: number;
  opportunities: number;
  countries: string[];
  xml_notices: number;
  latest_import: ImportRun | null;
  source: string;
  today: string;
};
export type Watch = {
  opportunity: Notice;
  stage: string;
  note: string;
  updated: boolean;
  changes?: Comparison | null;
};
export type SavedSearch = {
  mode?: string;
  id: number;
  name: string;
  query: string;
  country: string;
  status: string;
};
export type Profile = {
  description: string;
  countries: string[];
  exclusions: string[];
};
export type Answer = {
  publication_id: string;
  mode: string;
  claims: { answer: string; quote: string }[];
  unknown: string[];
  rejected_quotes: number;
  review_required?: boolean;
  model?: string;
};
export type Snapshot = {
  collection: Collection;
  notices: Notice[];
  imports: ImportRun[];
  generated_at: string;
};
