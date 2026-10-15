import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { FrustrationResult } from '@/lib/frustrationAnalyzer';
import type { TacticalLog } from '@/components/TacticalAnalysisTerminal';

const SEGMENTS = 24;
const TONE: Record<string, string> = { Low: 'bg-primary', Medium: 'bg-primary', High: 'bg-warning', Critical: 'bg-destructive' };
const SEV: Record<TacticalLog['severity'], string> = { low: 'text-faint', medium: 'text-warning', high: 'text-destructive', critical: 'text-destructive' };

/** The right-hand rail of the chat: how agitated the scammer is and which pressure tactics were detected. Display heuristics only; no decision depends on them. */
export function Instruments({ frustration, logs }: { frustration: FrustrationResult | null; logs: TacticalLog[] }) {
  const score = frustration?.score ?? 0;
  const filled = Math.round((score / 100) * SEGMENTS);
  const tone = frustration ? TONE[frustration.level] ?? 'bg-primary' : 'bg-line-strong';
  const counts = useMemo(() => ({
    urgency: logs.filter((l) => l.type === 'urgency').length,
    threats: logs.filter((l) => l.type === 'threat' || l.type === 'aggression').length,
    money: logs.filter((l) => l.type === 'financial').length,
  }), [logs]);

  return (
    <aside className="space-y-4">
      <section className="panel p-5">
        <div className="label-mono">Scammer agitation</div>
        <div className="mt-3 flex items-end justify-between">
          <span className="font-mono text-4xl font-medium tracking-tight text-foreground">{frustration ? score : '--'}<span className="text-xl text-faint">%</span></span>
          <span className={cn('font-pixel text-[11px] uppercase tracking-wider', frustration?.level === 'Critical' ? 'text-destructive' : frustration?.level === 'High' ? 'text-warning' : 'text-primary')}>{frustration?.level ?? 'waiting'}</span>
        </div>
        <div className="mt-4 flex gap-[3px]" role="meter" aria-label="Scammer agitation" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100}>
          {Array.from({ length: SEGMENTS }, (_, i) => <i key={i} className={cn('h-5 flex-1 rounded-[1px] transition-colors duration-500', i < filled ? tone : 'bg-surface-3')} />)}
        </div>
        {frustration && frustration.factors.length > 0 && (
          <ul className="mt-4 space-y-1.5 font-mono text-[12px]">
            {frustration.factors.slice(0, 3).map((f, i) => (
              <li key={i} className="flex justify-between gap-3 text-muted-foreground"><span className="truncate">{f.type}</span><span className={f.impact > 0 ? 'text-destructive' : 'text-primary'}>{f.impact > 0 ? '+' : ''}{f.impact}%</span></li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel p-5">
        <div className="flex items-center justify-between"><span className="label-mono">Pressure tactics</span><span className="font-mono text-[11px] text-faint">{logs.length} detected</span></div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          {([['urgency', counts.urgency], ['threats', counts.threats], ['money', counts.money]] as const).map(([l, n]) => (
            <div key={l} className="rounded-md border border-line bg-surface-2 py-2.5"><div className="font-mono text-xl text-foreground">{n}</div><div className="label-mono mt-0.5 text-[9.5px]">{l}</div></div>
          ))}
        </div>
        <ol className="mt-4 max-h-56 space-y-2 overflow-y-auto pr-1 font-mono text-[12px]">
          {logs.length === 0 && <li className="py-6 text-center text-faint">Messages are classified here as they arrive.</li>}
          {logs.slice(-12).reverse().map((l) => (
            <li key={l.id} className="flex gap-2 leading-snug"><span className="text-primary">&gt;</span><span className={SEV[l.severity]}>{l.type}</span><span className="text-muted-foreground">{l.message}</span></li>
          ))}
        </ol>
      </section>
      <p className="px-1 font-mono text-[10.5px] leading-relaxed text-faint">Display heuristics over message text. No decision depends on them.</p>
    </aside>
  );
}