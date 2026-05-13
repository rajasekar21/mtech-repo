// ─── Auth & Users ───────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  role: "admin" | "developer" | "viewer";
  organization_id: string;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  logo_url?: string;
  plan: "free" | "pro" | "enterprise";
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginRequest {
  email: string;
  password: string;
}

// ─── API Specifications ──────────────────────────────────────────────────────

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | "OPTIONS" | "HEAD";
export type RiskLevel = "critical" | "high" | "medium" | "low" | "none";
export type AuthMethod = "oauth2" | "api_key" | "basic" | "jwt" | "none";
export type SpecStatus = "active" | "deprecated" | "draft" | "archived";

export interface ApiSpec {
  id: string;
  name: string;
  version: string;
  description: string;
  status: SpecStatus;
  tags: string[];
  base_url?: string;
  openapi_version?: string;
  endpoints_count: number;
  flows_count: number;
  dependencies_count: number;
  governance_score?: number;
  risk_level: RiskLevel;
  auth_methods: AuthMethod[];
  uploaded_by: string;
  created_at: string;
  updated_at: string;
}

export interface ApiEndpoint {
  id: string;
  spec_id: string;
  path: string;
  method: HttpMethod;
  operation_id?: string;
  summary: string;
  description: string;
  tags: string[];
  risk_level: RiskLevel;
  auth_required: boolean;
  auth_method?: AuthMethod;
  deprecated: boolean;
  request_body?: JsonSchema;
  responses: Record<string, ResponseSchema>;
  parameters: Parameter[];
  security_findings?: SecurityFinding[];
  created_at: string;
  updated_at: string;
}

export interface Parameter {
  name: string;
  in: "query" | "header" | "path" | "cookie";
  required: boolean;
  description?: string;
  schema?: JsonSchema;
}

export interface ResponseSchema {
  description: string;
  content?: Record<string, { schema: JsonSchema }>;
}

export interface JsonSchema {
  type?: string;
  format?: string;
  properties?: Record<string, JsonSchema>;
  items?: JsonSchema;
  required?: string[];
  enum?: unknown[];
  description?: string;
  example?: unknown;
  $ref?: string;
  allOf?: JsonSchema[];
  oneOf?: JsonSchema[];
  anyOf?: JsonSchema[];
}

export interface ApiDependency {
  id: string;
  source_spec_id: string;
  target_spec_id: string;
  source_endpoint_id?: string;
  target_endpoint_id?: string;
  relationship_type: "CALLS" | "DEPENDS_ON" | "AUTHENTICATES_VIA" | "ROUTES_TO" | "USES";
  weight: number;
  description?: string;
  created_at: string;
}

export interface ApiVersion {
  id: string;
  spec_id: string;
  version: string;
  changelog?: string;
  breaking_changes: boolean;
  compatibility_score: number;
  created_at: string;
}

// ─── Flows ───────────────────────────────────────────────────────────────────

export type FlowType = "payment" | "authentication" | "authorization" | "data_sync" | "notification" | "generic";

export interface Flow {
  id: string;
  spec_id: string;
  name: string;
  description: string;
  type: FlowType;
  mermaid_diagram: string;
  steps: FlowStep[];
  involved_apis: string[];
  involved_endpoints: string[];
  created_at: string;
  updated_at: string;
}

export interface FlowStep {
  step_number: number;
  from: string;
  to: string;
  action: string;
  description?: string;
  endpoint_id?: string;
}

// ─── Architecture Entities ───────────────────────────────────────────────────

export type EntityType = "api" | "psp" | "bank" | "flow" | "auth" | "database" | "gateway" | "external";

export interface ArchitectureEntity {
  id: string;
  spec_id: string;
  name: string;
  type: EntityType;
  description?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

// ─── Search ──────────────────────────────────────────────────────────────────

export interface DocumentChunk {
  id: string;
  spec_id: string;
  content: string;
  chunk_type: "endpoint" | "schema" | "flow" | "description" | "example";
  endpoint_id?: string;
  flow_id?: string;
  metadata: Record<string, unknown>;
  similarity_score?: number;
}

export interface SearchResult {
  chunk: DocumentChunk;
  score: number;
  endpoint?: ApiEndpoint;
  spec?: ApiSpec;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
  spec_id?: string;
  processing_time_ms: number;
}

// ─── Security ────────────────────────────────────────────────────────────────

export type SecuritySeverity = "critical" | "high" | "medium" | "low" | "info";
export type SecurityCategory =
  | "authentication"
  | "authorization"
  | "input_validation"
  | "data_exposure"
  | "rate_limiting"
  | "encryption"
  | "injection"
  | "configuration"
  | "other";

export interface SecurityFinding {
  id: string;
  spec_id: string;
  endpoint_id?: string;
  title: string;
  description: string;
  severity: SecuritySeverity;
  category: SecurityCategory;
  affected_path?: string;
  affected_method?: HttpMethod;
  recommendation: string;
  cwe_id?: string;
  owasp_category?: string;
  false_positive: boolean;
  created_at: string;
}

// ─── Governance ──────────────────────────────────────────────────────────────

export type RuleStatus = "pass" | "fail" | "warning" | "skipped";
export type RuleCategory =
  | "naming"
  | "documentation"
  | "security"
  | "versioning"
  | "deprecation"
  | "schema"
  | "performance"
  | "compliance";

export interface GovernanceRule {
  id: string;
  name: string;
  description: string;
  category: RuleCategory;
  severity: SecuritySeverity;
  fix_suggestion?: string;
  documentation_url?: string;
}

export interface GovernanceRuleResult {
  rule: GovernanceRule;
  status: RuleStatus;
  affected_endpoints?: string[];
  details?: string;
  fix_suggestion?: string;
}

export interface GovernanceReport {
  id: string;
  spec_id: string;
  overall_score: number;
  passed: number;
  failed: number;
  warnings: number;
  skipped: number;
  rule_results: GovernanceRuleResult[];
  ai_recommendations?: string;
  created_at: string;
}

// ─── Impact Analysis ─────────────────────────────────────────────────────────

export type ChangeType =
  | "schema_change"
  | "endpoint_removal"
  | "auth_change"
  | "timeout_change"
  | "deprecation"
  | "breaking_change";

export interface ImpactRequest {
  spec_id: string;
  endpoint_id?: string;
  change_description: string;
  change_type: ChangeType;
}

export interface ImpactedApi {
  spec_id: string;
  spec_name: string;
  endpoint_id?: string;
  endpoint_path?: string;
  relationship_type: string;
  impact_severity: SecuritySeverity;
  description: string;
}

export interface ImpactedFlow {
  flow_id: string;
  flow_name: string;
  impact_description: string;
  severity: SecuritySeverity;
}

export interface ImpactReport {
  id: string;
  request: ImpactRequest;
  risk_score: number;
  impacted_apis: ImpactedApi[];
  impacted_flows: ImpactedFlow[];
  security_implications: string[];
  ai_recommendations: string;
  blast_radius: number;
  created_at: string;
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  sources?: DocumentChunk[];
  created_at: string;
}

export interface ChatConversation {
  id: string;
  title: string;
  spec_id?: string;
  message_count: number;
  last_message?: string;
  created_at: string;
  updated_at: string;
}

export interface ChatResponse {
  message: ChatMessage;
  conversation_id: string;
  sources: DocumentChunk[];
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  spec_id?: string;
}

// ─── Graph ───────────────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  label: string;
  type: EntityType;
  spec_id?: string;
  endpoint_count?: number;
  risk_level?: RiskLevel;
  metadata: Record<string, unknown>;
  x?: number;
  y?: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  weight?: number;
  label?: string;
  animated?: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  spec_id?: string;
  depth: number;
}

// ─── Pagination ──────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface FilterParams {
  page?: number;
  page_size?: number;
  search?: string;
  tags?: string[];
  risk_level?: RiskLevel;
  auth_method?: AuthMethod;
  deprecated?: boolean;
  status?: SpecStatus;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

// ─── Notifications ───────────────────────────────────────────────────────────

export type NotificationType = "info" | "success" | "warning" | "error";

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

// ─── Dashboard Stats ─────────────────────────────────────────────────────────

export interface DashboardStats {
  total_specs: number;
  total_endpoints: number;
  total_flows: number;
  total_dependencies: number;
  avg_governance_score: number;
  critical_findings: number;
  high_findings: number;
  recent_uploads: number;
}

export interface RecentActivity {
  id: string;
  type: "upload" | "analysis" | "chat" | "governance" | "impact";
  description: string;
  spec_name?: string;
  created_at: string;
  user?: Pick<User, "id" | "name" | "avatar_url">;
}
