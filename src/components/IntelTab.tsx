import { useState } from 'react';
import { Check, Copy, DownloadSimple as Download, SealCheck as FileCheck2, ShieldWarning as ShieldAlert, ShieldSlash as ShieldX } from '@phosphor-icons/react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { download } from '@/lib/api';
import { toast } from '@/hooks/use-toast';
import type { SessionDetail } from '@/lib/types';
import { cn } from '@/lib/utils';

const RISK: Record<string, string> = { url: 'text-destructive', upi: 'text-destructive', bank_account: 'text-destructive', ifsc: 'text-warning', phone: 'text-warning' };
const SHOWN = ['psp_app', 'issuing_bank', 'bank', 'branch', 'city', 'state', 'registrar', 'registered', 'abuse_email', 'domain'];

export function IntelTab({ detail }: { detail: SessionDetail }) {
  const [copied, setCopied] = useState('');
  const { ledger, iocs, canaries, session } = detail;
  const humans = canaries.filter((c) => c.alert);
  const bots = canaries.length - humans.length;
  const dl = (path: string, name: string) => download(path, name).catch((e) => toast({ title: 'Download failed', description: String(e), variant: 'destructive' }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
      <div className="lg:col-span-7 space-y-3">
        <h3 className="label-mono">Payment details captured ({iocs.length}). Each appears word for word in the scammer's messages.</h3>
        {iocs.length === 0 && <p className="text-sm text-muted-foreground font-mono rounded-lg border border-border/40 p-4">Nothing captured yet. Only artifacts that literally appear in the scammer's messages are recorded.</p>}
        {iocs.map((i) => {
          const facts = Object.entries(i.enrichment ?? {}).filter(([k, v]) => SHOWN.includes(k) && v);
          return (
            <div key={`${i.kind}:${i.value}`} className="panel p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className={cn('text-[10px] font-mono uppercase', RISK[i.kind])}>{i.kind.replace('_', ' ')}</div>
                  <div className="font-mono text-sm break-all">{i.value}</div>
                </div>
                <Button size="sm" variant="ghost" className="h-7 w-7 p-0" aria-label="copy"
                        onClick={() => { void navigator.clipboard.writeText(i.value); setCopied(i.value); setTimeout(() => setCopied(''), 1500); }}>
                  {copied === i.value ? <Check className="h-3 w-3 text-primary" /> : <Copy className="h-3 w-3" />}
                </Button>
              </div>
              {facts.length > 0 && <div className="flex flex-wrap gap-1.5 mt-2">{facts.map(([k, v]) => <Badge key={k} variant="outline" className="text-[10px] font-mono">{k}: {String(v)}</Badge>)}</div>}
            </div>
          );
        })}
      </div>

      <div className="lg:col-span-5 space-y-4">
        <div className={cn('rounded-lg border p-4 space-y-2', ledger.ok ? 'border-primary/40 bg-primary/5' : 'border-destructive/50 bg-destructive/10')}>
          <div className="flex items-center gap-2 font-mono text-sm">
            {ledger.ok ? <FileCheck2 className="h-4 w-4 text-primary" /> : <ShieldX className="h-4 w-4 text-destructive" />}
            Record integrity: {ledger.ok ? 'verified' : 'tampered'}
          </div>
          <div className="font-mono text-[11px] text-muted-foreground break-all">{ledger.events} chained events • head {ledger.head_hash}</div>
          {!ledger.ok && <div className="font-mono text-[11px] text-destructive">{ledger.reason} {ledger.bad_seq ? `(event #${ledger.bad_seq})` : ''}</div>}
          <div className="flex gap-2 pt-1">
            <Button size="sm" className="font-mono text-xs gap-1" onClick={() => dl(`/api/sessions/${session.id}/report.pdf`, `sentinel-${session.id.slice(0, 8)}.pdf`)}><Download className="h-3 w-3" />PDF report</Button>
            <Button size="sm" variant="outline" className="font-mono text-xs gap-1" onClick={() => dl(`/api/sessions/${session.id}/proof.json`, `proof-${session.id.slice(0, 8)}.json`)}><Download className="h-3 w-3" />Proof JSON</Button>
          </div>
          <p className="text-[10px] font-mono text-muted-foreground">Verify offline: <code>python -m sentinel.verify proof.json</code></p>
        </div>

        <div className="panel p-4 space-y-2">
          <div className="flex items-center gap-2 label-mono"><ShieldAlert className="h-3 w-3" />Link trap</div>
          <div className="font-mono text-[11px] text-muted-foreground">{humans.length} human open(s) • {bots} link-preview crawler fetch(es) ignored (no alert)</div>
          {humans.map((c, i) => (
            <div key={i} className="rounded border border-destructive/30 bg-destructive/5 p-2 font-mono text-[11px] space-y-0.5">
              <div className="text-destructive">THEY OPENED YOUR LINK • {new Date(c.at).toLocaleString()}</div>
              <div>IP {c.ip || '?'} • {c.subnet || 'unknown'}</div>
              <div>{c.isp || 'ISP unknown'} {c.asn && `• ${c.asn}`}</div>
              {c.fingerprint_hash && <div className="break-all text-muted-foreground">fp {c.fingerprint_hash.slice(0, 24)}… {String(c.fingerprint?.platform ?? '')} {String(c.fingerprint?.screen ?? '')} {String(c.fingerprint?.timezone ?? '')}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}