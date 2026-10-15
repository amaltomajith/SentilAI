import { useEffect, useMemo, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Microphone, ShieldCheck, ShieldWarning } from '@phosphor-icons/react';
import { Bubble, Typing } from '@/components/chat/Bubble';
import { ManualInput } from '@/components/ManualInput';
import { MediaAttachment } from '@/components/MediaAttachment';
import { Instruments } from '@/components/Instruments';
import { Sprite } from '@/components/pixel/Sprite';
import { analyzeScammerIntent, type TacticalLog } from '@/components/TacticalAnalysisTerminal';
import { calculateFrustration } from '@/lib/frustrationAnalyzer';
import { api } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import type { SessionDetail } from '@/lib/types';
import { cn } from '@/lib/utils';

const VERDICT: Record<string, string> = {
  pass: 'border-primary/40 text-primary', repaired: 'border-warning/50 text-warning', fallback: 'border-destructive/50 text-destructive', bypassed: 'border-destructive text-destructive',
};
const pretty = (s: string) => s.replace(/_/g, ' ');

export function ConversationTab({ detail }: { detail: SessionDetail }) {
  const qc = useQueryClient();
  const end = useRef<HTMLDivElement>(null);
  const { session, turns } = detail;
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [turns.length]);

  const scammer = turns.filter((t) => t.role === 'scammer');
  const frustration = scammer.length ? calculateFrustration(scammer[scammer.length - 1].text) : null;
  const logs: TacticalLog[] = useMemo(
    () => scammer.flatMap((t) => analyzeScammerIntent(t.text).map((l) => ({ ...l, id: `${t.seq}-${l.id}`, timestamp: new Date(t.at) }))),
    [turns.length], // eslint-disable-line react-hooks/exhaustive-deps
  );
  const lastAgent = [...turns].reverse().find((t) => t.role === 'agent');
  const strategy = lastAgent?.gate?.strategy;
  const waiting = session.status === 'active' && turns.length > 0 && turns[turns.length - 1].role === 'scammer' && Date.now() - new Date(turns[turns.length - 1].at).getTime() < 25_000;

  async function send(text: string) {
    try {
      await api(`/api/sessions/${session.id}/messages`, { method: 'POST', json: { text } });
      qc.invalidateQueries({ queryKey: ['session', session.id] });
    } catch (e) { toast({ title: 'Error', description: e instanceof Error ? e.message : String(e), variant: 'destructive' }); }
  }

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="panel flex h-[min(74dvh,700px)] min-h-[460px] flex-col overflow-hidden">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-5 py-3.5">
          <span className="font-mono text-[14px] text-foreground">{session.channel === 'whatsapp' ? `+${session.peer}` : pretty(session.scenario || session.kind)}</span>
          <span className={session.status === 'active' ? 'tag-pixel' : 'tag-line'}>{session.status === 'active' ? 'live' : pretty(session.status)}</span>
          {strategy && <span className="tag-line">{pretty(strategy.scam_type)}</span>}
          {strategy && strategy.language !== 'English' && <span className="tag-line">{strategy.language}</span>}
          <span className="ml-auto flex items-center gap-3 font-mono text-[11px] text-faint">
            <span>{session.exchanges} exchanges</span>
            <span className={detail.ledger.ok ? 'text-primary/90' : 'text-destructive'}>{detail.ledger.ok ? 'chain intact' : 'chain broken'}</span>
          </span>
        </header>

        {session.status === 'halted_benign' && (
          <div className="flex items-center gap-2 border-b border-primary/20 bg-forest/60 px-5 py-2.5 text-[13px] text-bone"><ShieldCheck size={16} className="text-primary" />Engagement stopped: this looks like a genuine message, so Sentinel did not reply.</div>
        )}
        {session.status === 'halted_uncertain' && (
          <div className="flex items-center gap-2 border-b border-warning/30 bg-warning/5 px-5 py-2.5 text-[13px] text-warning"><ShieldWarning size={16} />Could not classify this message with confidence, so no reply was sent.</div>
        )}

        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-6">
          {turns.length === 0 && (
            <div className="grid h-full place-items-center text-center">
              <div><Sprite name="eye" size={64} className="mx-auto opacity-90" /><p className="mt-4 text-sm text-muted-foreground">Waiting for the first message.</p></div>
            </div>
          )}
          {turns.map((t) => (
            <Bubble
              key={t.seq}
              role={t.role}
              tag={<>
                {t.media_kind === 'voice' && <span className="tag-line inline-flex items-center gap-1"><Microphone size={10} />voice</span>}
                {t.role === 'agent' && t.gate?.verdict && <span className={cn('rounded-sm border px-1.5 py-[2px] font-pixel text-[9.5px] uppercase leading-none tracking-wider', VERDICT[t.gate.verdict])}>{t.gate.verdict}</span>}
              </>}
              meta={<span title={`#${t.seq} ${t.hash}`}>{new Date(t.at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}{t.role === 'agent' ? ` · ${t.latency_ms} ms` : ''}</span>}
            >
              <p className="whitespace-pre-wrap">{t.text}</p>
              {t.gate?.media?.map((m) => <MediaAttachment key={m.sha256} kind={m.kind} sha256={m.sha256} />)}
              {t.original_text && t.original_text !== t.text && <p className="mt-1.5 text-xs italic text-muted-foreground">original: {t.original_text}</p>}
            </Bubble>
          ))}
          {waiting && <Typing />}
          <div ref={end} />
        </div>

        {session.kind === 'manual' && session.status !== 'closed' && <ManualInput onSubmit={send} isProcessing={false} />}
      </section>
      <Instruments frustration={frustration} logs={logs} />
    </div>
  );
}