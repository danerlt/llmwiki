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
}
export interface PageOut {
  id: string;
  kb_id: string;
  title: string;
  slug: string;
  page_type: string;
}
export interface PageDetail extends PageOut {
  content_md: string;
  frontmatter: Record<string, unknown>;
  source_ids: string[];
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
export interface Citation {
  page_id: string;
  title: string;
  kb_id: string;
}
export interface AnswerOut {
  answer: string;
  citations: Citation[];
}
