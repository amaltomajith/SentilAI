import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, FilePlus as FilePlus2, PaperPlaneTilt as Send, X } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { useTakedowns } from '@/lib/hooks';
import { toast } from '@/hooks/use-toast';
import type { TakedownRow } from '@/lib/types';
import { cn } from '@/lib/utils';

const ST: Record<string, string> = { drafted: 'border-warning/50 text-warning', approved: 'border-line-strong text-foreground', rejected: 'border-muted-foreground/40 text-muted-foreground', dispatched: 'border-primary/50 text-primary' };

function Card({ t }: { t: TakedownRow }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const act = async (a: 'approve' | 'reject' | 'dispatch') => {
    try { await api(`/api/takedowns/${t.id}/${a}`, { method: 'POST' }); qc.invalidateQueries({ queryKey: ['takedowns'] }); qc.invalidateQueries({ queryKey: ['session', t.session_id] }); }
    catch (e) { toast({ title: 'Blocked', description: e instanceof Error ? e.message : String(e), variant: 'destructive' }); }
  };
  return (
    <div className="panel p-4 space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="font-mono text-sm break-all"><span className="text-muted-foreground text-xs uppercase mr-2">{t.kind.replace('_', ' ')}</span>{t.target}</div>
        <Badge variant="outline" className={cn('text-[10px] font-mono', ST[t.status])}>{t.status}{t.status === 'dispatched' ? ' (dry-run)' : ''}</Badge>
      </div>
      <div className="font-mono text-[11px] text-muted-foreground">to: {t.recipient}</div>
      <div className="flex gap-2 flex-wrap">
        <Button size="sm" variant="outline" className="font-mono text-xs h-7" onClick={() => setOpen(!open)}>{open ? 'hide' : 'inspect'} report + STIX</Button>
        {t.status === 'drafted' && <>
          <Button size="sm" className="font-mono text-xs h-7 gap-1" onClick={() => act('approve')}><Check className="h-3 w-3" />Approve</Button>
          <Button size="sm" variant="ghost" className="font-mono text-xs h-7 gap-1" onClick={() => act('reject')}><X className="h-3 w-3" />Reject</Button>
        </>}
        {t.status === 'approved' && <Button size="sm" className="font-mono text-xs h-7 gap-1" onClick={() => act('dispatch')}><Send className="h-3 w-3" />Dispatch (dry-run)</Button>}
      </div>
      {open && (
        <div className="grid md:grid-cols-2 gap-2">
          <pre className="text-[11px] font-mono bg-background/60 rounded p-2 overflow-auto max-h-72 whitespace-pre-wrap">{t.report}</pre>
          <pre className="text-[11px] font-mono bg-background/60 rounded p-2 overflow-auto max-h-72">{JSON.stringify(t.bundle, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export function TakedownTab({ sessionId }: { sessionId: string | null }) {
  const qc = useQueryClient();
  const { data } = useTakedowns();
  async function draft() {
    if (!sessionId) return;
    try {
      const r = await api<TakedownRow[]>(`/api/sessions/${sessionId}/takedowns/draft`, { method: 'POST' });
      toast({ title: r.length ? `${r.length} takedown draft(s) created` : 'Nothing new to draft' });
      qc.invalidateQueries({ queryKey: ['takedowns'] });
    } catch (e) { toast({ title: 'Error', description: e instanceof Error ? e.message : String(e), variant: 'destructive' }); }
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg border border-warning/30 bg-warning/5 p-3">
        <p className="text-xs font-mono text-warning max-w-2xl">Human-in-the-loop queue. Nothing is ever sent automatically: reports are drafted, you approve, and dispatch is <b>dry-run</b> only (writes the report and STIX bundle to <code>backend/data/outbox/</code>).</p>
        <Button size="sm" className="font-mono text-xs gap-1" onClick={draft} disabled={!sessionId}><FilePlus2 className="h-3 w-3" />Draft from selected session</Button>
      </div>
      {data?.length === 0 && <p className="text-sm font-mono text-muted-foreground">No takedown drafts yet.</p>}
      {data?.map((t) => <Card key={t.id} t={t} />)}
    </div>
  );
}