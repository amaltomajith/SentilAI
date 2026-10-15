import { useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { QRCodeSVG } from 'qrcode.react';
import { CheckCircle, Link as LinkIcon, Phone, ShieldCheck, Trash, LinkBreak } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { api } from '@/lib/api';
import { useTargets, useWhatsApp } from '@/lib/hooks';
import { normalizeNumber, validNumber } from '@/lib/phone';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

const fail = (e: unknown) => toast({ title: 'Error', description: e instanceof Error ? e.message : String(e), variant: 'destructive' });

function Step({ n, title, done, children }: { n: number; title: string; done?: boolean; children: ReactNode }) {
  return (
    <section className="panel p-6">
      <div className="mb-5 flex items-center gap-3">
        <span className={cn('font-pixel text-[13px]', done ? 'text-primary' : 'text-faint')}>{`0${n}`}</span>
        <h2 className="text-lg font-semibold tracking-tight text-foreground">{title}</h2>
        {done && <CheckCircle size={18} weight="fill" className="ml-auto text-primary" />}
      </div>
      {children}
    </section>
  );
}

/** QR inside a scanner frame: corner brackets and a sweep line. The QR itself is the real WhatsApp link code. */
function Scanner({ value }: { value: string }) {
  return (
    <div className="relative mx-auto w-fit rounded-md border border-primary/30 bg-bone p-4">
      <QRCodeSVG value={value} size={200} bgColor="transparent" fgColor="#06100A" />
      {(['left-0 top-0 border-l-2 border-t-2', 'right-0 top-0 border-r-2 border-t-2', 'bottom-0 left-0 border-b-2 border-l-2', 'bottom-0 right-0 border-b-2 border-r-2'] as const).map((c) => <i key={c} className={cn('absolute h-5 w-5 border-forest', c)} />)}
      <i className="absolute inset-x-3 top-0 h-px animate-sweep bg-primary shadow-[0_0_12px_hsl(143_76%_62%)]" />
    </div>
  );
}

export function LinkStep() {
  const qc = useQueryClient();
  const wa = useWhatsApp();
  const [phone, setPhone] = useState('');
  const [usePhone, setUsePhone] = useState(false);
  const s = wa.data;

  async function askCode() {
    try { await api('/api/whatsapp/pairing-code', { method: 'POST', json: { phone: normalizeNumber(phone).number } }); qc.invalidateQueries({ queryKey: ['whatsapp'] }); }
    catch (e) { fail(e); }
  }
  async function startLink() {
    try { await api('/api/whatsapp/link', { method: 'POST' }); qc.invalidateQueries({ queryKey: ['whatsapp'] }); } catch (e) { fail(e); }
  }
  async function unlink() {
    if (!window.confirm('Unlink WhatsApp from Sentinel? The agent stops reading and replying until you link again.')) return;
    try { await api('/api/whatsapp/logout', { method: 'POST' }); qc.invalidateQueries({ queryKey: ['whatsapp'] }); } catch (e) { fail(e); }
  }

  return (
    <Step n={1} title="Link your WhatsApp" done={s?.state === 'open'}>
      {!s || !s.bridge_online ? (
        <div className="space-y-2 rounded-md border border-warning/30 bg-warning/5 p-4 text-sm">
          <p className="text-warning">The WhatsApp connector is not running.</p>
          <p className="font-mono text-[12.5px] text-muted-foreground">cd whatsapp-bridge, then npm run dev</p>
        </div>
      ) : s.state === 'open' ? (
        <div className="space-y-4">
          <p className="text-[15px] text-foreground">Linked{s.me ? <> as <span className="font-mono">+{s.me}</span></> : null}. Sentinel only reads the number in step two.</p>
          <Button size="sm" variant="outline" onClick={unlink}><LinkBreak size={15} />Unlink</Button>
        </div>
      ) : s.state === 'qr' ? (
        <div className="space-y-5">
          {!usePhone && s.qr && (
            <div className="space-y-4">
              <Scanner value={s.qr} />
              <p className="text-center text-[13px] leading-relaxed text-muted-foreground">WhatsApp, Settings, Linked devices, Link a device, then scan. The code refreshes about every 20 seconds.</p>
            </div>
          )}
          {s.pairing_code && (
            <div className="space-y-2 text-center">
              <div className="font-mono text-3xl tracking-[0.35em] text-primary">{s.pairing_code}</div>
              <p className="text-[13px] text-muted-foreground">In Linked devices choose <b className="font-medium text-foreground">Link with phone number instead</b> and type this code.</p>
            </div>
          )}
          {usePhone && !s.pairing_code && (
            <div className="flex gap-2">
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="your WhatsApp number" className="font-mono" inputMode="tel" aria-label="Your WhatsApp number" />
              <Button onClick={askCode} disabled={!validNumber(normalizeNumber(phone).number)}>Get code</Button>
            </div>
          )}
          <button onClick={() => setUsePhone(!usePhone)} className="mx-auto flex items-center gap-1.5 text-[13px] text-primary underline-offset-4 hover:underline">
            {usePhone ? <><LinkIcon size={14} />Use the QR code instead</> : <><Phone size={14} />Only have this one phone? Link with a code</>}
          </button>
        </div>
      ) : s.state === 'not_linked' || s.state === 'logged_out' ? (
        <div className="space-y-4">
          {s.state === 'logged_out' && <p className="text-sm text-warning">WhatsApp was unlinked from your phone. Link it again to continue.</p>}
          <p className="text-[14px] leading-relaxed text-muted-foreground">Sentinel appears as a linked device on your WhatsApp. It only ever reads the chat you choose in step two.</p>
          <Button onClick={startLink}>Link my WhatsApp</Button>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground cmd-caret">Connecting to WhatsApp</p>
      )}
    </Step>
  );
}

export function TargetStep() {
  const qc = useQueryClient();
  const flagged = useTargets();
  const [raw, setRaw] = useState('');
  const norm = normalizeNumber(raw);
  const ok = validNumber(norm.number);

  async function add() {
    try {
      const r = await api<{ number: string; assumed_country_code_91: boolean }>('/api/targets', { method: 'POST', json: { number: raw } });
      toast({ title: `Now engaging +${r.number}`, description: r.assumed_country_code_91 ? 'No country code given, so +91 (India) was assumed.' : undefined });
      setRaw(''); qc.invalidateQueries({ queryKey: ['targets'] });
    } catch (e) { fail(e); }
  }
  async function stop(n: string) {
    try { await api(`/api/targets/${n}`, { method: 'DELETE' }); qc.invalidateQueries({ queryKey: ['targets'] }); } catch (e) { fail(e); }
  }

  return (
    <Step n={2} title="Paste the scammer's number" done={!!flagged.data?.length}>
      <form onSubmit={(e) => { e.preventDefault(); if (ok) void add(); }} className="space-y-2.5">
        <div className="flex items-center gap-2 rounded-md border border-line-strong bg-surface-2 pl-3 focus-within:border-primary/60">
          <span className="font-mono text-primary" aria-hidden>&gt;</span>
          <Input value={raw} onChange={(e) => setRaw(e.target.value)} placeholder="+91 98765 43210" className="border-0 bg-transparent font-mono shadow-none hover:border-0 focus-visible:border-0 focus-visible:shadow-none" inputMode="tel" aria-label="Scammer's number" />
          <Button type="submit" size="sm" disabled={!ok} className="mr-1.5">Engage</Button>
        </div>
        {raw && <p className="px-1 font-mono text-[12px] text-muted-foreground">{ok ? <>Will engage <span className="text-foreground">+{norm.number}</span>{norm.assumed91 ? ' (+91 assumed)' : ''}</> : 'Include the country code, for example +91.'}</p>}
      </form>
      {!!flagged.data?.length && (
        <ul className="mt-4 space-y-2">
          {flagged.data.map((n) => (
            <li key={n} className="flex items-center justify-between rounded-md border border-primary/30 bg-forest px-3.5 py-2.5 font-mono text-[13.5px]">
              <span className="text-foreground">+{n}</span>
              <span className="flex items-center gap-3"><span className="tag-pixel">engaged</span>
                <button aria-label={`Stop engaging ${n}`} title="Stop engaging" onClick={() => stop(n)} className="text-muted-foreground transition-colors hover:text-destructive"><Trash size={16} /></button></span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-5 flex gap-2 text-[13px] leading-relaxed text-muted-foreground"><ShieldCheck size={17} className="mt-0.5 shrink-0 text-primary" />
        Only messages from these numbers are read or answered. Every other chat stays on your phone. Remove a number to stop instantly.</p>
    </Step>
  );
}