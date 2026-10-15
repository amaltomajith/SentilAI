import { useState } from 'react';
import { CaretDown as ChevronDown, CaretRight as ChevronRight, Wrench } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import type { SessionDetail, Trace } from '@/lib/types';
import { cn } from '@/lib/utils';

function TraceRow({ t }: { t: Trace }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-border/40 bg-muted/20">
      <button className="w-full flex items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(!open)}>
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        <Wrench className="h-3 w-3 text-foreground" />
        <span className="font-mono text-xs text-foreground">{t.tool}</span>
        <Badge variant="outline" className={cn('text-[9px] h-4', t.ok ? 'border-primary/40 text-primary' : 'border-destructive/50 text-destructive')}>{t.ok ? 'ok' : 'error'}</Badge>
        <span className="ml-auto font-mono text-[10px] text-muted-foreground">{t.latency_ms} ms • {new Date(t.at).toLocaleTimeString()}</span>
      </button>
      {open && (
        <div className="grid md:grid-cols-2 gap-2 px-3 pb-3">
          <div><div className="text-[10px] font-mono text-muted-foreground mb-1">ARGS</div><pre className="text-[11px] font-mono bg-background/60 rounded p-2 overflow-auto max-h-48">{JSON.stringify(t.args, null, 2)}</pre></div>
          <div><div className="text-[10px] font-mono text-muted-foreground mb-1">RESULT</div><pre className="text-[11px] font-mono bg-background/60 rounded p-2 overflow-auto max-h-48">{JSON.stringify(t.result, null, 2)}</pre></div>
        </div>
      )}
    </div>
  );
}

export function TraceTab({ detail }: { detail: SessionDetail }) {
  const agent = detail.turns.filter((t) => t.role === 'agent');
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <h3 className="label-mono">Safety check: draft versus approved reply</h3>
        {agent.length === 0 && <p className="text-sm text-muted-foreground font-mono">No agent replies yet.</p>}
        {agent.map((t) => {
          const changed = t.draft !== t.text;
          return (
            <div key={t.seq} className="panel p-4 space-y-3">
              <div className="flex flex-wrap items-center gap-2 font-mono text-[11px]">
                <span className="text-foreground">Turn #{t.seq}</span>
                <Badge variant="outline" className={cn('text-[10px]', t.gate.verdict === 'pass' ? 'border-primary/40 text-primary' : 'border-warning/50 text-warning')}>verdict: {t.gate.verdict}</Badge>
                <span className="text-muted-foreground">total {t.latency_ms} ms</span>
                {t.gate.draft_ms !== undefined && <span className="text-muted-foreground">model {t.gate.draft_ms} ms</span>}
                {t.gate.provider && <Badge variant="outline" className="text-[10px] border-line-strong text-foreground">{t.gate.provider}</Badge>}
              </div>
              <div className="grid md:grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] font-mono text-muted-foreground mb-1">MODEL DRAFT</div>
                  <p className={cn('text-sm rounded p-2 whitespace-pre-wrap', changed ? 'bg-destructive/10 border border-destructive/30' : 'bg-muted/30')}>{t.draft || 'none'}</p>
                </div>
                <div>
                  <div className="text-[10px] font-mono text-muted-foreground mb-1">FINAL (SENT)</div>
                  <p className="text-sm rounded p-2 bg-primary/10 border border-primary/30 whitespace-pre-wrap">{t.text}</p>
                </div>
              </div>
              {t.gate.strategy && (
                <div className="rounded-md border border-line-strong bg-surface-3 p-2 font-mono text-[11px] space-y-1">
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    <span>scam type: <b className="text-foreground">{t.gate.strategy.scam_type.replace('_', ' ')}</b></span>
                    <span>stage: <b className="text-foreground">{t.gate.strategy.stage.replace('_', ' ')}</b></span>
                    <span>pressure: <b className="text-foreground">{t.gate.strategy.pressure}</b></span>
                    <span>their language: <b className="text-foreground">{t.gate.strategy.language}</b></span>
                    <span>chosen tactic: <b className="text-primary">{t.gate.strategy.tactic.replace(/_/g, ' ')}</b></span>
                  </div>
                  {Object.keys(t.gate.strategy.candidates).length > 0 && (
                    <div className="text-muted-foreground">considered: {Object.entries(t.gate.strategy.candidates).map(([k, v]) => `${k.replace(/_/g, ' ')} (${v})`).join(' · ')}</div>
                  )}
                </div>
              )}
              {t.gate.violations && t.gate.violations.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {t.gate.violations.map((v, i) => <Badge key={i} variant="outline" className="text-[10px] font-mono border-destructive/40 text-destructive">{v.code}: {v.detail}</Badge>)}
                </div>
              )}
              {t.gate.llm_note && <p className="text-[11px] font-mono text-warning">{t.gate.llm_note}</p>}
            </div>
          );
        })}
      </section>
      <section className="space-y-2">
        <h3 className="label-mono">MCP tool calls ({detail.traces.length})</h3>
        {detail.traces.map((t, i) => <TraceRow key={i} t={t} />)}
        {detail.traces.length === 0 && <p className="text-sm text-muted-foreground font-mono">No tool calls yet.</p>}
      </section>
    </div>
  );
}