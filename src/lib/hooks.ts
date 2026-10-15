import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, startStream } from './api';
import type { GraphData, Health, Me, ProfileResp, WaState, Scenario, SessionDetail, SessionSummary, TakedownRow } from './types';

export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/api/health'), refetchInterval: 30_000 });
export const useScenarios = () => useQuery({ queryKey: ['scenarios'], queryFn: () => api<Scenario[]>('/api/scenarios') });
export const useSessions = (enabled = true) => useQuery({ queryKey: ['sessions'], queryFn: () => api<SessionSummary[]>('/api/sessions'), enabled });
export const useSession = (id: string | null) =>
  useQuery({ queryKey: ['session', id], queryFn: () => api<SessionDetail>(`/api/sessions/${id}`), enabled: !!id });
export const useGraph = () => useQuery({ queryKey: ['graph'], queryFn: () => api<GraphData>('/api/graph') });
export const useTakedowns = () => useQuery({ queryKey: ['takedowns'], queryFn: () => api<TakedownRow[]>('/api/takedowns') });
export const useWhatsApp = () => useQuery({ queryKey: ['whatsapp'], queryFn: () => api<WaState>('/api/whatsapp'), refetchInterval: 3000 });
export const useTargets = () => useQuery({ queryKey: ['targets'], queryFn: () => api<string[]>('/api/targets') });
export const useMe = (enabled = true) => useQuery({ queryKey: ['me'], queryFn: () => api<Me>('/api/me'), enabled });
export const useProfile = (enabled = true) => useQuery({ queryKey: ['profile'], queryFn: () => api<ProfileResp>('/api/profile'), enabled });

/** Backend is the single source of truth: every live event just invalidates the relevant queries. */
export function useLiveSync(enabled: boolean): boolean {
  const qc = useQueryClient();
  const [live, setLive] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    return startStream((e) => {
      if (e.type === 'wa_status') { qc.invalidateQueries({ queryKey: ['whatsapp'] }); return; }
      qc.invalidateQueries({ queryKey: ['sessions'] });
      qc.invalidateQueries({ queryKey: ['session', e.session_id] });
      if (e.type === 'ioc' || e.type.startsWith('canary')) qc.invalidateQueries({ queryKey: ['graph'] });
    }, setLive);
  }, [enabled, qc]);
  return live;
}