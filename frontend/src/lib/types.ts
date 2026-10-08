export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Company {
  id: number;
  bin: string;
  name: string;
  is_supplier: boolean;
  is_customer: boolean;
  region: string;
  city: string;
  legacy_risk_score: number;
  legacy_score_interpretation: string;
}

export interface KgdSavedResult {
  observation_id: number;
  observed_at: string;
  parser_version: string;
  stale: boolean;
  taxpayer_type?: string;
  taxpayer_name?: string;
  registration_begin?: string | null;
  registration_end?: string | null;
  total_arrears?: string;
  tax_arrears?: string;
  pension_arrears?: string;
  social_arrears?: string;
  health_insurance_arrears?: string;
  reporting_dates?: string[];
}

export interface KgdSummary {
  source: string;
  status: "success" | "not_found" | "unavailable" | "invalid" | "not_checked";
  latest_observation_id: number | null;
  latest_observed_at: string | null;
  source_url: string;
  last_successful: KgdSavedResult | null;
}

export interface CompanyDetail extends Company {
  oked: string;
  company_status: string;
  registration_date: string | null;
  address: string;
  phone: string;
  email: string;
  description: string;
  resident_status: string;
  company_size: string;
  kopf: string;
  economic_sector: string;
  website: string | null;
  created_at: string;
  updated_at: string;
  adata_updated_at: string | null;
  kgd_checks: KgdSummary[];
}

export interface Person {
  id: number;
  full_name: string;
  is_verified: boolean;
  identity_status: "identifier_verified" | "unverified";
  history_status: string;
}

export interface EntitySourceReference {
  observation_id: number;
  source: string;
  status: string;
  observed_at: string;
  parser_version: string;
  url: string | null;
}

export interface Directorship {
  id: number;
  company: Company;
  person: Person | null;
  observed_name: string;
  identity_status: string;
  identity_verified: boolean;
  is_current: boolean;
  currently_applicable: boolean | null;
  temporal_status:
    "unknown" | "in_period" | "not_in_period" | "observed_inactive";
  start_date: string | null;
  end_date: string | null;
  observed_from: string | null;
  observed_until: string | null;
  source: string;
  source_reference: EntitySourceReference | null;
}

export interface Ownership extends Directorship {
  share_percent: string | null;
}

export interface Contract {
  id: number;
  contract_number: string;
  contract_gos_id: number | null;
  tender_id: string;
  title: string;
  amount: string;
  contract_date: string | null;
  winner: boolean;
  supplier: Company;
  customer: Company | null;
  customer_name: string;
  customer_bin: string;
  source_url: string | null;
  source_observation_id: number | null;
  created_at: string;
}

export interface GraphSnapshot {
  id: number;
  version: number;
  graph_hash: string;
  algorithm_version: string;
  state: string;
  as_of: string;
  member_ids: number[];
  changes: Partial<Record<"added_members" | "removed_members", number[]>> &
    Partial<
      Record<
        | "added_nodes"
        | "removed_nodes"
        | "added_edges"
        | "removed_edges"
        | "changed_edges"
        | "changed_nodes",
        string[]
      >
    >;
  previous_id: number | null;
  created_at: string;
}

export type ClusterConnectionType = RelationshipType | "mixed_roles";

export interface ClusterDirectory {
  title: string;
  companies: { id: number; name: string; bin: string }[];
  additional_companies: number;
  reasons: {
    type: ClusterConnectionType;
    label: string;
    company_count: number;
  }[];
  primary_reason: {
    type: ClusterConnectionType;
    label: string;
    company_count: number;
  } | null;
  analysis_status: "not_calculated" | "stale" | "ready";
  analysis_as_of: string | null;
  review_priority: number | null;
  coverage: {
    status: "not_assessed" | "no_checks" | "partial" | "checked";
    checked: number | null;
    total: number;
    as_of: string | null;
  };
}

export interface Cluster {
  directory?: ClusterDirectory;
  uuid: string;
  name: string;
  is_active: boolean;
  review_priority: number | null;
  company_count: number;
  current_snapshot: GraphSnapshot | null;
  created_at: string;
  updated_at: string;
}

export interface SourceReference {
  source: string;
  observation_id?: number;
  record_id?: number;
  url: string;
  quality?: string;
  observed_at?: string | null;
}

export interface GraphNode {
  id: string;
  kind: "company" | "person" | "contact";
  name: string;
  bin?: string;
  company_id?: number;
  contact_type?: string;
  identity_verified?: boolean;
}

export type RelationshipType =
  "director" | "owner" | "address" | "phone" | "email";

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  value: string;
  company_id: number;
  confidence: string;
  valid_from: string | null;
  valid_until: string | null;
  temporal_status: string;
  common_contact?: boolean;
  evidence: SourceReference[];
  limitations: string[];
}

export interface GraphPayload {
  nodes: GraphNode[];
  links: GraphEdge[];
}

export interface GraphResponse {
  cluster: string;
  version: number | null;
  snapshot_id: number | null;
  graph_hash: string | null;
  state: string;
  historical: boolean;
  graph: GraphPayload;
}

export interface Lineage {
  source_snapshot_id: number;
  source_cluster: string;
  source_version: number;
  target_snapshot_id: number;
  target_cluster: string;
  target_version: number;
  kind: string;
  shared_member_ids: number[];
}

export interface SnapshotDetail extends GraphSnapshot {
  cluster: string;
  graph: GraphPayload;
  incoming_transitions: Lineage[];
  outgoing_transitions: Lineage[];
}

export interface FindingEvidence {
  kind: string;
  id: string;
  source?: string;
  url: string;
  observed_at?: string | null;
  quality?: string;
}

export interface Finding {
  id: string;
  code: string;
  rule_version: string;
  company_ids: number[];
  evidence: FindingEvidence[];
  statements: string[];
  candidate_contribution: number;
  contribution: number;
  dimension: string;
  limitations: string[];
}

export interface AnalysisMetrics {
  review_priority: number;
  relationship_priority: number;
  financial_priority: number;
  link_strength: number;
  behavioural_risk: number | null;
  behavioural_status: string;
  company_count: number;
  fresh_arrears_checks: number;
  unknown_current_arrears: number;
  retained_recent_arrears_results: number;
  companies_with_fresh_arrears: number[];
  score_interpretation: string;
  stored_contract_count: number;
  stored_contract_amount: string;
  shared_customer_count: number;
  score_categories: Partial<
    Record<"director" | "owner" | "contacts" | "cross_role", number>
  >;
  score_breakdown: { finding_id: string; points: number }[];
}

export interface AnalysisSnapshot {
  id: number;
  version: number;
  graph_snapshot_id: number;
  graph_version: number;
  analysis_hash: string;
  rules_version: string;
  as_of: string;
  created_at: string;
  metrics: AnalysisMetrics;
  findings: Finding[];
  limitations: string[];
}

export interface ExplanationDocument {
  version: string;
  summary: string;
  narrative?: {
    paragraphs: { text: string; finding_ids: string[] }[];
    checks: { text: string; finding_ids: string[] }[];
  };
  findings: {
    finding_id: string;
    title: string;
    fact: string;
    details?: string[];
    meaning: string;
    companies: { id: number; name: string; bin: string }[];
    additional_companies: number;
    notes: string[];
  }[];
  additional_findings: number;
  checks: string[];
  coverage: string[];
  score: {
    value: number;
    items: { finding_id: string; label: string; points: number }[];
    meaning: string;
  };
  conclusion: string;
}

export interface Explanation {
  id: number;
  analysis_id: number;
  text: string;
  language: string;
  provider: string;
  model: string;
  prompt_version: string;
  status: string;
  created_at: string;
  document: ExplanationDocument | null;
}

export interface AnalysisResponse {
  cluster: string;
  graph_version: number | null;
  status: "not_calculated" | "ready" | "stale";
  historical: boolean;
  analysis: AnalysisSnapshot | null;
  explanation: Explanation | null;
}

export interface SnapshotEvidence {
  id: string;
  kind: string;
  graph_snapshot_id: number;
  graph_edge?: GraphEdge;
  source?: string;
  observation_id?: number;
  contract_id?: number;
  url?: string;
  quality?: string;
  observed_at?: string | null;
  status?: string;
  parser_version?: string;
  company_id?: number | null;
}

export interface ViewPayload {
  positions?: Record<string, { x: number; y: number; pinned: boolean }>;
  zoom?: { x: number; y: number; k: number };
  filters?: RelationshipType[];
  selected?: string | null;
  frozen?: boolean;
}

export interface GraphView {
  revision: number;
  payload: ViewPayload | null;
  snapshot_version?: number;
  schema_version?: number;
}

export interface SessionUser {
  id: number | null;
  username: string | null;
  email?: string | null;
  role: "anonymous" | "user" | "staff";
}

export interface AccountProfile {
  username: string;
  email: string;
  role: "user" | "staff";
  date_joined: string;
}

export interface AccountSavedView {
  cluster_uuid: string;
  cluster_name: string;
  cluster_is_active: boolean;
  saved_snapshot_version: number;
  current_snapshot_version: number | null;
  revision: number;
  updated_at: string;
}

export interface AccountRegistration {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface Capabilities {
  can_save_views: boolean;
  can_start_jobs: boolean;
}

export interface Session {
  user: SessionUser;
  capabilities: Capabilities;
  csrf_token: string;
}

export interface Job {
  job: string;
  kind: "graph" | "analysis";
  status: string;
  error_code: string;
  created_at: string;
  finished_at: string | null;
  created?: boolean;
  url?: string;
  summary?: Partial<
    Record<
      | "analyzed"
      | "groups"
      | "created"
      | "updated"
      | "unchanged"
      | "retired"
      | "affected_companies"
      | "snapshots_created"
      | "analysis_versions_created",
      number
    >
  >;
  results?: {
    cluster_uuid: string;
    version: number;
    graph_hash: string;
    state: string;
    analysis_version?: number;
    analysis_hash?: string;
  }[];
  result?: {
    cluster_uuid: string;
    graph_snapshot_id: number;
    graph_version: number;
    graph_hash: string;
    analysis_id: number | null;
    analysis_version: number | null;
    analysis_hash: string | null;
    explanation_id: number | null;
  };
}
