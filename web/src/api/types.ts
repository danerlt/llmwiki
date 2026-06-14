export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: string;
  department_id: string | null;
}
export interface KB {
  id: string;
  scope_type: string;
  scope_ref_id: string | null;
  name: string;
  page_count?: number;
}
export interface Stats {
  kb_count: number;
  page_count: number;
  source_count: number;
  pending_reviews: number;
}
export interface Department {
  id: string;
  name: string;
  parent_id: string | null;
}
export interface Team {
  id: string;
  name: string;
}
export interface PageOut {
  id: string;
  kb_id: string;
  title: string;
  slug: string;
  page_type: string;
  tags?: string[];
}
export interface SourceRef {
  id: string;
  filename: string;
}
export interface SearchHit extends PageOut {
  snippet: string;
  matched: string;
}
export interface PageDetail extends PageOut {
  content_md: string;
  frontmatter: Record<string, unknown>;
  source_ids: string[];
  updated_at?: string | null;
  backlinks?: PageOut[];
  outlinks?: PageOut[];
  sources?: SourceRef[];
}
export interface SourceOut {
  id: string;
  kb_id: string;
  filename: string;
  content_type: string;
  status: string;
  error: string | null;
  job_id: string | null;
}
export interface Comment {
  id: string;
  page_id: string;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
}
export interface PageVersion {
  version_no: number;
  title: string;
  page_type: string;
  content_md: string;
  edited_by: string | null;
  created_at: string;
}
export interface Citation {
  index: number;
  page_id: string;
  title: string;
  kb_id: string;
}
export interface AnswerOut {
  answer: string;
  citations: Citation[];
}
export interface PromotionOut {
  id: string;
  page_id: string;
  page_title: string;
  to_kb_id: string;
  to_kb_name: string;
  requested_by: string;
  status: string;
  note: string | null;
}
export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface AuditEventOut {
  id: string;
  actor_id: string;
  actor_email: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}
