export type Role = "student" | "teacher" | "admin";
export interface User {
  id: string;
  username: string;
  name: string;
  role: Role;
  service: string;
  group_name: string;
  active: boolean;
}
export interface Card {
  number: string;
  address: string;
  description: string;
  incident_type: string;
  incident_code: string;
  caller_name: string;
  caller_phone: string;
  casualties: "unknown" | "no" | "yes";
  services: string[];
}
export interface Contact {
  id: string;
  name: string;
  role: string;
  phone: string;
  greeting?: string;
  reply?: string;
}
export interface Fact {
  confirmed_by_contact_ids?: string[];
  id: string;
  label: string;
  patterns: string[];
  critical: boolean;
}
export interface Scenario {
  id: string;
  title: string;
  description: string;
  service: string;
  difficulty: "basic" | "intermediate" | "advanced";
  objective: string;
  status: "draft" | "approved" | "archived";
  version: number;
  owner_id: string;
  card: Card;
  contacts: Contact[];
  expected_statuses: string[];
  required_facts: Fact[];
  reference_response: string;
  response_limit_seconds: number;
  completion_limit_seconds: number;
  source_note: string;
  created_at: string;
  updated_at: string;
}
export interface Event {
  id: string;
  client_event_id: string;
  kind: string;
  at: string;
  elapsed_seconds: number;
  payload: Record<string, unknown>;
}
export interface Criterion {
  id: string;
  title: string;
  category: string;
  status: "pass" | "fail" | "review";
  points: number;
  max_points: number;
  critical: boolean;
  actual: string;
  expected: string;
  explanation: string;
  evidence_ids: string[];
  source: string;
}
export interface Report {
  score: number;
  max_score: number;
  requires_review: boolean;
  critical_errors: number;
  summary: string;
  mode: string;
  reaction_seconds: number | null;
  duration_seconds: number;
  first_update_seconds?: number | null;
  criteria: Criterion[];
  strengths: string[];
  recommendations: string[];
  criterion_review_revision?: number;
  criterion_reviews?: Record<string, CriterionDecision>;
  expert_assessment?: {
    score: number;
    max_score: number;
    requires_review: boolean;
    critical_errors: number;
  };
  teacher_review_stale?: boolean;
  teacher_review: null | {
    score: number;
    comment: string;
    reviewed_at: string;
    reviewer_name: string;
    criterion_revision?: number;
  };
  generated_at: string;
}
export interface CriterionDecision {
  status: Criterion["status"];
  comment: string;
  evidence_ids: string[];
  reviewed_at: string;
  reviewer_name: string;
  revision: number;
}
export interface Session {
  id: string;
  scenario_id: string;
  scenario_title: string;
  scenario_version: number;
  student_id: string;
  student_name: string;
  teacher_id: string;
  service: string;
  mode: "practice" | "exam";
  status: "assigned" | "active" | "submitted" | "reviewed" | "stopped";
  assigned_at: string;
  started_at: string | null;
  finished_at: string | null;
  card: Card;
  contacts: Contact[];
  objective: string;
  response_limit_seconds: number;
  completion_limit_seconds: number;
  current_status: string | null;
  draft: Record<string, string>;
  events: Event[];
  report: Report | null;
}
export interface Meta {
  name: string;
  demo_mode: boolean;
  version: string;
  ai_mode: string;
  status_labels: Record<string, string>;
  services: string[];
}
export interface Analytics {
  total_sessions: number;
  completed_sessions: number;
  active_sessions: number;
  stopped_sessions: number;
  pending_review_sessions: number;
  average_score: number | null;
  scored_sessions: number;
  average_reaction_seconds: number | null;
  criteria: { id: string; title: string; failed: number; total: number }[];
  recent_sessions: Session[];
}
export interface EventResult {
  event: Event;
  session: Session;
  reply: null | { text: string; call_id: string };
}
export interface ClassifierItem {
  code: string;
  label: string;
  group: string;
  features: string[];
  primary_service: string | null;
  source_row: number;
  routing?: Record<string, unknown>;
  source_file?: string;
}
export interface KnowledgeItem {
  id: string;
  title: string;
  body: string;
  source: string;
}
export const STATUS_LABELS: Record<string, string> = {
  accepted: "Принята",
  rejected: "Не принята",
  responding: "Начало реагирования",
  arrived: "Прибытие",
  working: "Проведение работ",
  refused: "Отказ от выполнения работ",
  completed: "Работы завершены",
};
export const SESSION_LABELS: Record<string, string> = {
  assigned: "Назначено",
  active: "В работе",
  submitted: "Ожидает проверки",
  reviewed: "Проверено",
  stopped: "Остановлено",
};
export const LEVEL_LABELS: Record<string, string> = {
  basic: "Базовый",
  intermediate: "Средний",
  advanced: "Продвинутый",
};
