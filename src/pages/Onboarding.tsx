import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { Lock } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Sprite } from '@/components/pixel/Sprite';
import { api } from '@/lib/api';
import { useMe, useProfile } from '@/lib/hooks';
import type { ProfileData } from '@/lib/types';
import { toast } from '@/hooks/use-toast';

const LANGS = ['English', 'Hindi', 'Hinglish', 'Malayalam', 'Tamil', 'Telugu', 'Kannada', 'Marathi', 'Bengali', 'Gujarati', 'Punjabi', 'Urdu'];
const fail = (e: unknown) => toast({ title: 'Could not save', description: e instanceof Error ? e.message : String(e), variant: 'destructive' });
const SELECT = 'h-10 w-full rounded-md border border-line-strong bg-surface-2 px-3 text-sm text-foreground hover:border-primary/30 focus-visible:border-primary/60';

function Consent({ onDone }: { onDone: () => void }) {
  const [ok, setOk] = useState(false);
  return (
    <div className="panel relative mx-auto max-w-2xl overflow-hidden p-8 sm:p-10">
      <Sprite name="lock" size={72} tilt={8} className="absolute right-6 top-6 hidden sm:block" />
      <h1 className="max-w-[18ch] text-3xl font-semibold tracking-tightest sm:text-4xl">Before we start.</h1>
      <ul className="mt-6 max-w-[56ch] space-y-3 text-[15px] leading-relaxed text-muted-foreground">
        <li>Sentinel replies from <b className="font-medium text-foreground">your WhatsApp account</b>, in your name, to the one number you give it. It wastes a scammer's time and collects evidence.</li>
        <li>Use it only against someone who <b className="font-medium text-foreground">contacted you first</b> and looks like a scammer. It never starts a chat and never pays or shares real bank details.</li>
        <li>Never aim it at a person you know, or at anyone to harass them. That is misuse and may be illegal.</li>
        <li>Messages with that number are stored with a tamper-evident log so you can report them. Your profile is read by an AI model, except the private fields you mark.</li>
        <li>WhatsApp does not allow unofficial clients, so the linked account could be restricted. A secondary number is safer.</li>
      </ul>
      <label className="mt-7 flex items-start gap-3 text-[15px]"><Checkbox checked={ok} onCheckedChange={(v) => setOk(v === true)} className="mt-0.5" />I understand, and I will use Sentinel only this way.</label>
      <Button size="lg" disabled={!ok} className="mt-6" onClick={async () => { try { await api('/api/consent', { method: 'POST', json: { accept: true } }); onDone(); } catch (e) { fail(e); } }}>Continue</Button>
    </div>
  );
}

export default function Onboarding() {
  const me = useMe();
  const prof = useProfile();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileData>({});
  const [share, setShare] = useState<Record<string, boolean>>({});
  const [optIn, setOptIn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (prof.data) { setForm(prof.data.data); setShare(prof.data.share); setOptIn(prof.data.collective_opt_in); } }, [prof.data]);
  const set = <K extends keyof ProfileData>(k: K, v: ProfileData[K]) => setForm((f) => ({ ...f, [k]: v }));
  const shared = (k: string) => share[k] !== false;
  const langs = form.languages ?? [];

  if (me.isLoading || prof.isLoading) return <div className="grid place-items-center py-32"><Sprite name="eye" size={56} className="animate-pulse" /></div>;
  if (!me.data?.consented) return <Consent onDone={() => qc.invalidateQueries({ queryKey: ['me'] })} />;

  const Share = ({ k }: { k: string }) => (
    <label className="mt-2 flex items-center gap-2.5 text-[12px] text-muted-foreground"><Switch checked={shared(k)} onCheckedChange={(v) => setShare((s) => ({ ...s, [k]: v }))} aria-label={`The agent may mention ${k}`} />The agent may mention this</label>
  );

  async function save() {
    setBusy(true);
    try {
      await api('/api/profile', { method: 'PUT', json: { data: { ...form, age: form.age ? Number(form.age) : undefined }, share, collective_opt_in: optIn } });
      await qc.invalidateQueries({ queryKey: ['profile'] });
      toast({ title: 'Saved', description: 'Now rehearse against a sample scam.' });
      navigate('/practice');
    } catch (e) { fail(e); } finally { setBusy(false); }
  }
  const canSave = !!(form.alias?.trim() && form.age && form.occupation?.trim());

  return (
    <div className="grid gap-10 lg:grid-cols-[300px_minmax(0,1fr)] lg:gap-16">
      <div className="lg:sticky lg:top-24 lg:self-start">
        <h1 className="text-3xl font-semibold tracking-tightest sm:text-4xl">Tell the agent about you.</h1>
        <p className="mt-4 text-[15px] leading-relaxed text-muted-foreground">There is no fixed character. The agent plays a believable version of you, so the scammer's pitch fits and keeps going.</p>
        <dl className="mt-8 space-y-5 text-[14px]">
          <div><dt className="label-mono text-primary/90">Mentionable</dt><dd className="mt-1 leading-relaxed text-muted-foreground">Shared with the AI only if its switch is on.</dd></div>
          <div><dt className="label-mono text-primary/90">Private</dt><dd className="mt-1 leading-relaxed text-muted-foreground">Never sent to the AI. Only used to block those details from replies.</dd></div>
          <div><dt className="label-mono text-primary/90">Never ask</dt><dd className="mt-1 leading-relaxed text-muted-foreground">Bank, card, UPI, OTP, password or ID numbers are rejected.</dd></div>
        </dl>
      </div>

      <div className="space-y-5">
        <section className="panel space-y-6 p-6 sm:p-7">
          <div className="grid gap-5 sm:grid-cols-2">
            <div><Label htmlFor="alias">Name the agent uses</Label><Input id="alias" className="mt-1.5" value={form.alias ?? ''} onChange={(e) => set('alias', e.target.value)} placeholder="Anita" maxLength={30} /></div>
            <div><Label htmlFor="age">Age</Label><Input id="age" type="number" className="mt-1.5" value={form.age ?? ''} onChange={(e) => set('age', e.target.value ? Number(e.target.value) : undefined)} min={16} max={100} /><Share k="age" /></div>
            <div><Label htmlFor="job">What you do</Label><Input id="job" className="mt-1.5" value={form.occupation ?? ''} onChange={(e) => set('occupation', e.target.value)} placeholder="School teacher, retired clerk, student" /><Share k="occupation" /></div>
            <div><Label htmlFor="city">City or area</Label><Input id="city" className="mt-1.5" value={form.city ?? ''} onChange={(e) => set('city', e.target.value)} placeholder="Pune" /><Share k="city" /></div>
          </div>
          <div>
            <Label>Languages you speak</Label>
            <div className="mt-2.5 flex flex-wrap gap-2">
              {LANGS.map((l) => {
                const on = langs.includes(l);
                return <button key={l} type="button" aria-pressed={on} onClick={() => set('languages', on ? langs.filter((x) => x !== l) : [...langs, l])}
                               className={on ? 'rounded-sm border border-primary/50 bg-forest px-3 py-1.5 text-[13px] text-foreground' : 'rounded-sm border border-line-strong px-3 py-1.5 text-[13px] text-muted-foreground hover:border-primary/30 hover:text-foreground'}>{l}</button>;
              })}
            </div>
            <p className="mt-2 text-[12px] text-faint">The agent mirrors a scammer's language only if you speak it.</p>
          </div>
          <div className="grid gap-5 sm:grid-cols-3">
            <div><Label htmlFor="form">How you write</Label>
              <select id="form" className={`${SELECT} mt-1.5`} value={form.formality ?? ''} onChange={(e) => set('formality', (e.target.value || undefined) as ProfileData['formality'])}><option value="">No preference</option><option value="formal">Formal and polite</option><option value="casual">Casual</option></select></div>
            <div><Label htmlFor="tech">Comfort with banking apps</Label>
              <select id="tech" className={`${SELECT} mt-1.5`} value={form.tech_comfort ?? ''} onChange={(e) => set('tech_comfort', (e.target.value || undefined) as ProfileData['tech_comfort'])}><option value="">Not set</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></div>
            <label className="flex items-end gap-2.5 pb-2.5 text-sm"><Checkbox checked={!!form.uses_emoji} onCheckedChange={(v) => set('uses_emoji', v === true)} />Uses emoji</label>
          </div>
          <div><Label htmlFor="sit">Your situation</Label><Textarea id="sit" className="mt-1.5" value={form.situation ?? ''} onChange={(e) => set('situation', e.target.value)} rows={2} placeholder="Lives alone, small pension, son works abroad" /><Share k="situation" /></div>
          <div><Label htmlFor="extra">Anything else the agent should know</Label><Textarea id="extra" className="mt-1.5" value={form.extra ?? ''} onChange={(e) => set('extra', e.target.value)} rows={2} placeholder="Habits, how you react to unknown messages" /><Share k="extra" /></div>
        </section>

        <section className="relative space-y-5 overflow-hidden rounded-md border border-warning/25 bg-surface-1 p-6 sm:p-7">
          <div className="flex items-center gap-2.5 text-warning"><Lock size={18} /><h2 className="text-lg font-semibold tracking-tight">Private vault</h2></div>
          <p className="max-w-[60ch] text-[14px] leading-relaxed text-muted-foreground">Optional. These never reach the AI. Sentinel only uses them to make sure they never appear in a reply.</p>
          <div className="grid gap-5 sm:grid-cols-2">
            <div><Label htmlFor="fn">Your full legal name</Label><Input id="fn" className="mt-1.5" value={form.full_name ?? ''} onChange={(e) => set('full_name', e.target.value)} /></div>
            <div><Label htmlFor="emp">Employer or school</Label><Input id="emp" className="mt-1.5" value={form.employer ?? ''} onChange={(e) => set('employer', e.target.value)} /></div>
            <div><Label htmlFor="addr">Home address</Label><Input id="addr" className="mt-1.5" value={form.address ?? ''} onChange={(e) => set('address', e.target.value)} /></div>
            <div><Label htmlFor="own">Your own WhatsApp number</Label><Input id="own" className="mt-1.5 font-mono" value={form.own_phone ?? ''} onChange={(e) => set('own_phone', e.target.value)} placeholder="+91" inputMode="tel" /></div>
          </div>
        </section>

        <label className="flex items-start gap-3 rounded-md border border-line px-5 py-4 text-[14px] leading-relaxed text-muted-foreground"><Checkbox checked={optIn} onCheckedChange={(v) => setOptIn(v === true)} className="mt-0.5" />
          <span>Help the agent learn. Share anonymous counters of which tactics worked: never messages, numbers or anything about you.</span></label>

        <div className="sticky bottom-4 flex justify-end"><Button size="lg" onClick={save} disabled={!canSave || busy} className="shadow-[0_18px_40px_-14px_hsl(150_60%_2%)]">{busy ? 'Saving' : 'Save and practice'}</Button></div>
      </div>
    </div>
  );
}