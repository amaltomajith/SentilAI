export interface SessionSummary {
  id: string; kind: string; channel: string; peer: string; status: string; scenario: string;
  exchanges: number; iocs: number; head_hash: string; created_at: string;
}
export interface GateViolation { code: string; detail: string }
export interface StrategyInfo { scam_type: string; stage: string; pressure: string; language: string; tactic: string; candidates: Record<string, number> }
export interface GateInfo {
  strategy?: StrategyInfo;
  media?: { kind: 'image' | 'voice'; sha256: string }[];
  verdict?: string; violations?: GateViolation[]; llm_note?: string; provider?: string | null; draft_ms?: number;
}
export interface Turn {
  seq: number; role: 'scammer' | 'agent'; text: string; original_text: string; media_kind: string;
  draft: string; gate: GateInfo; latency_ms: number; hash: string; at: string;
}
export interface Ioc { kind: string; value: string; enrichment: Record<string, unknown> }
export interface Trace {
  tool: string; args: Record<string, unknown>; result: Record<string, unknown>; ok: boolean; latency_ms: number; turn_seq: number; at: string;
}
export interface CanaryRow {
  token: string; kind: string; classification: 'human' | 'crawler'; ip: string; subnet: string; asn: string; isp: string;
  fingerprint: Record<string, unknown>; fingerprint_hash: string; at: string; alert: boolean;
}
export interface TakedownRow {
  id: string; session_id: string; kind: string; target: string; recipient: string; status: string; mode: string;
  report: string; bundle: Record<string, unknown>; created_at: string;
}
export interface LedgerInfo { ok: boolean; events: number; head_hash: string; reason: string; bad_seq: number | null }
export interface SessionDetail {
  session: SessionSummary; turns: Turn[]; iocs: Ioc[]; traces: Trace[]; canaries: CanaryRow[];
  takedowns: Pick<TakedownRow, 'id' | 'kind' | 'target' | 'recipient' | 'status' | 'mode'>[]; ledger: LedgerInfo;
}
export interface GraphNode { id: string; type: string; label: string; ring: number | null }
export interface GraphRing {
  sessions: string[]; size: number; confidence: 'high' | 'mixed' | 'low'; score: number; shared_artifact_kinds: string[];
  links: { a: string; b: string; weight: number; shared: { kind: string; value: string; weight: number }[] }[];
}
export interface GraphData { nodes: GraphNode[]; edges: { source: string; target: string; weight: number }[]; rings: GraphRing[] }
export interface Health {
  ok: boolean; llm_providers: string[]; takedown_mode: string; bridge_auth_configured: boolean; admin_configured: boolean;
}
export interface WaState {
  bridge_online: boolean; state: 'not_linked' | 'linking' | 'connecting' | 'qr' | 'open' | 'logged_out';
  qr: string | null; pairing_code: string | null; me: string | null; scope: string;
}
export interface Me { id: string; consented: boolean; collective_opt_in: boolean }
export interface ProfileData {
  alias?: string; age?: number; occupation?: string; city?: string; languages?: string[]; formality?: 'formal' | 'casual'; uses_emoji?: boolean;
  style_notes?: string; tech_comfort?: 'low' | 'medium' | 'high'; situation?: string; extra?: string;
  full_name?: string; employer?: string; address?: string; own_phone?: string;
}
export interface ProfileResp { data: ProfileData; share: Record<string, boolean>; complete: boolean; collective_opt_in: boolean }
export interface Scenario { id: string; category: 'scam' | 'safe'; type: string; message: string }
export interface LiveEvent { type: string; session_id: string; data: Record<string, unknown>; ts: number }