import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Badge } from '@/components/ui/badge';
import { useGraph } from '@/lib/hooks';
import { cn } from '@/lib/utils';

const TYPE_COLOR: Record<string, string> = {
  session: '#22c55e', upi: '#ef4444', bank_account: '#f97316', ifsc: '#eab308', phone: '#a855f7',
  url: '#ef4444', domain: '#ef4444', fingerprint: '#06b6d4', subnet: '#38bdf8', asn: '#64748b',
};
const CONF: Record<string, string> = { high: 'border-destructive/60 text-destructive', mixed: 'border-warning/60 text-warning', low: 'border-muted-foreground/50 text-muted-foreground' };

export function GraphTab({ onSelectSession }: { onSelectSession: (id: string) => void }) {
  const { data } = useGraph();
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(700);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el); setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  const graph = useMemo(() => ({
    nodes: (data?.nodes ?? []).map((n) => ({ ...n })),
    links: (data?.edges ?? []).map((e) => ({ ...e })),
  }), [data]);

  if (!data) return <p className="text-sm font-mono text-muted-foreground">Loading attribution graph…</p>;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div ref={box} className="lg:col-span-8 panel overflow-hidden h-[520px]">
        {graph.nodes.length === 0
          ? <div className="h-full flex items-center justify-center text-muted-foreground/60 font-mono text-sm">No sessions with captured artifacts yet.</div>
          : <ForceGraph2D width={w} height={520} graphData={graph} backgroundColor="rgba(0,0,0,0)" cooldownTicks={80}
              nodeRelSize={5} linkColor={() => 'rgba(148,163,184,0.35)'} linkWidth={(l: object) => 1 + ((l as { weight: number }).weight ?? 0) * 2}
              nodeLabel={(n: object) => `${(n as { type: string }).type}: ${(n as { label: string }).label}`}
              nodeColor={(n: object) => TYPE_COLOR[(n as { type: string }).type] ?? '#94a3b8'}
              nodeVal={(n: object) => ((n as { type: string }).type === 'session' ? 4 : 1.5)}
              onNodeClick={(n: object) => { const id = (n as { id: string }).id; if (id.startsWith('session:')) onSelectSession(id.slice(8)); }} />}
      </div>
      <div className="lg:col-span-4 space-y-3">
        <h3 className="label-mono">Threat rings ({data.rings.length})</h3>
        {data.rings.length === 0 && <p className="text-sm font-mono text-muted-foreground rounded-lg border border-border/40 p-4">No sessions share an artifact yet. Rings appear when different sessions reuse a UPI ID, account, domain, device fingerprint or (weakly) an IFSC branch / network subnet.</p>}
        {data.rings.map((r, i) => (
          <div key={i} className="panel p-3 space-y-2">
            <div className="flex items-center justify-between font-mono text-xs">
              <span>Ring {i + 1} • {r.size} sessions</span>
              <Badge variant="outline" className={cn('text-[10px]', CONF[r.confidence])}>{r.confidence} confidence</Badge>
            </div>
            <div className="flex flex-wrap gap-1">{r.shared_artifact_kinds.map((k) => <Badge key={k} variant="outline" className="text-[10px] font-mono">{k}</Badge>)}</div>
            <div className="space-y-1">
              {r.links.slice(0, 4).map((l, j) => (
                <div key={j} className="text-[10px] font-mono text-muted-foreground">
                  <button className="underline" onClick={() => onSelectSession(l.a)}>{l.a.slice(0, 6)}</button> ↔ <button className="underline" onClick={() => onSelectSession(l.b)}>{l.b.slice(0, 6)}</button> via {l.shared.map((s) => s.kind).join(', ')}
                </div>
              ))}
            </div>
            {r.confidence !== 'high' && <p className="text-[10px] font-mono text-warning">Held together partly by weak links (shared branch/subnet can be coincidence). Treat as a lead, not proof.</p>}
          </div>
        ))}
      </div>
    </div>
  );
}