import { useSessions } from '@/lib/hooks';
import type { SessionSummary } from '@/lib/types';
import { cn } from '@/lib/utils';

export function SessionList({ title, filter, selected, onSelect, empty }: {
  title: string; filter: (s: SessionSummary) => boolean; selected: string | null; onSelect: (id: string) => void; empty: string;
}) {
  const sessions = useSessions();
  const list = (sessions.data ?? []).filter(filter);
  return (
    <div className="panel p-3">
      <div className="label-mono mb-3 flex justify-between px-2 pt-1"><span>{title}</span><span className="text-faint">{list.length}</span></div>
      <ul className="max-h-[460px] space-y-1 overflow-y-auto">
        {sessions.isLoading && [0, 1, 2].map((i) => <li key={i} className="h-14 animate-pulse rounded-md bg-surface-2" />)}
        {list.map((s) => (
          <li key={s.id}>
            <button onClick={() => onSelect(s.id)} className={cn('w-full rounded-md border px-3 py-2.5 text-left transition-colors', s.id === selected ? 'border-primary/40 bg-forest' : 'border-transparent hover:bg-surface-2')}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate font-mono text-[13px] text-foreground">{s.channel === 'whatsapp' ? `+${s.peer}` : (s.scenario || s.kind).replace(/-/g, ' ')}</span>
                <span className={s.status === 'active' ? 'tag-pixel' : 'tag-line'}>{s.status === 'active' ? 'live' : s.status.replace('_', ' ')}</span>
              </div>
              <div className="mt-1 font-mono text-[11px] text-faint">{s.exchanges} exchanges · {s.iocs} details · {new Date(s.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
            </button>
          </li>
        ))}
        {!sessions.isLoading && list.length === 0 && <li className="px-3 py-8 text-center text-[13px] leading-relaxed text-muted-foreground">{empty}</li>}
      </ul>
    </div>
  );
}