import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { ChatTeardropText, Play } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { SessionList } from '@/components/SessionList';
import { ConversationTab } from '@/components/ConversationTab';
import { TraceTab } from '@/components/TraceTab';
import { Sprite } from '@/components/pixel/Sprite';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { useScenarios, useSession } from '@/lib/hooks';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

export default function Practice() {
  const qc = useQueryClient();
  const scenarios = useScenarios();
  const [scenario, setScenario] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState('chat');
  const detail = useSession(selected);
  const fail = (e: unknown) => toast({ title: 'Error', description: e instanceof Error ? e.message : String(e), variant: 'destructive' });

  async function run() {
    try {
      const r = await api<{ session_id: string }>('/api/simulations', { method: 'POST', json: { scenario_id: scenario || null, turns: 4 } });
      setSelected(r.session_id); setTab('chat'); qc.invalidateQueries({ queryKey: ['sessions'] });
    } catch (e) { fail(e); }
  }
  async function manual() {
    try {
      const r = await api<{ session_id: string }>('/api/sessions', { method: 'POST', json: { kind: 'manual' } });
      setSelected(r.session_id); setTab('chat'); qc.invalidateQueries({ queryKey: ['sessions'] });
    } catch (e) { fail(e); }
  }

  return (
    <div className="space-y-8">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tightest sm:text-4xl">Rehearse before it goes live.</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Nothing here touches WhatsApp. The agent uses your profile exactly as it will in a real chat. Check that the replies sound like you.</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-24 lg:self-start">
          <div className="panel p-4">
            <div className="label-mono mb-3 px-1">Pick a scam</div>
            <ul className="max-h-64 space-y-1 overflow-y-auto">
              {[{ id: '', type: 'Surprise me', category: 'scam' as const }, ...(scenarios.data ?? [])].map((s) => (
                <li key={s.id || 'random'}>
                  <button onClick={() => setScenario(s.id)} aria-pressed={scenario === s.id} className={cn('flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-[13.5px] transition-colors', scenario === s.id ? 'border-primary/40 bg-forest text-foreground' : 'border-transparent text-muted-foreground hover:bg-surface-2 hover:text-foreground')}>
                    {s.type}{s.category === 'safe' && <span className="tag-line">genuine</span>}
                  </button>
                </li>
              ))}
            </ul>
            <div className="mt-4 space-y-2">
              <Button onClick={run} className="w-full"><Play size={15} weight="fill" />Watch a simulated scammer</Button>
              <Button onClick={manual} variant="outline" className="w-full"><ChatTeardropText size={16} />I'll type as the scammer</Button>
            </div>
          </div>
          <SessionList title="Practice chats" filter={(s) => s.channel !== 'whatsapp'} selected={selected} onSelect={(id) => { setSelected(id); setTab('chat'); }} empty="Pick a scam above to start." />
          <Button asChild size="lg" className="w-full"><Link to="/connect">Sounds like me. Connect WhatsApp</Link></Button>
        </aside>
        <section className="min-w-0">
          <Tabs value={tab} onValueChange={setTab}>
            <TabsList><TabsTrigger value="chat">Conversation</TabsTrigger><TabsTrigger value="why">Why it replied that way</TabsTrigger></TabsList>
            <div className="mt-6">
              {!detail.data && (
                <div className="panel grid place-items-center px-6 py-24 text-center">
                  <div><Sprite name="shield" size={72} className="mx-auto" /><p className="mt-5 text-lg font-semibold tracking-tight">No practice chat open.</p><p className="mx-auto mt-2 max-w-[40ch] text-sm leading-relaxed text-muted-foreground">Start one on the left, then check the replies.</p></div>
                </div>
              )}
              <TabsContent value="chat">{detail.data && <ConversationTab detail={detail.data} />}</TabsContent>
              <TabsContent value="why">{detail.data && <TraceTab detail={detail.data} />}</TabsContent>
            </div>
          </Tabs>
        </section>
      </div>
    </div>
  );
}