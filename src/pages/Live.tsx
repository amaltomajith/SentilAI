import { useEffect, useState } from 'react';
import { SessionList } from '@/components/SessionList';
import { ConversationTab } from '@/components/ConversationTab';
import { TraceTab } from '@/components/TraceTab';
import { IntelTab } from '@/components/IntelTab';
import { GraphTab } from '@/components/GraphTab';
import { TakedownTab } from '@/components/TakedownTab';
import { Sprite } from '@/components/pixel/Sprite';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useSession, useSessions } from '@/lib/hooks';

export default function Live() {
  const sessions = useSessions();
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState('conversation');
  const detail = useSession(selected);

  useEffect(() => {
    if (selected) return;
    const first = sessions.data?.find((x) => x.channel === 'whatsapp');
    if (first) setSelected(first.id);
  }, [sessions.data, selected]);

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside><SessionList title="Conversations" filter={(s) => s.channel === 'whatsapp'} selected={selected} onSelect={(id) => { setSelected(id); setTab('conversation'); }}
                          empty="Nothing yet. When the number you added messages you, the chat appears here." /></aside>
      <section className="min-w-0">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="conversation">Conversation</TabsTrigger>
            <TabsTrigger value="trace">Why it replied</TabsTrigger>
            <TabsTrigger value="intel">Evidence</TabsTrigger>
            <TabsTrigger value="graph">Scammer links</TabsTrigger>
            <TabsTrigger value="takedowns">Takedowns</TabsTrigger>
          </TabsList>
          <div className="mt-6">
            {tab !== 'graph' && tab !== 'takedowns' && !detail.data && (
              <div className="panel grid place-items-center px-6 py-24 text-center">
                <div><Sprite name="eye" size={72} className="mx-auto" /><p className="mt-5 text-lg font-semibold tracking-tight">Waiting for the scammer.</p>
                  <p className="mx-auto mt-2 max-w-[44ch] text-sm leading-relaxed text-muted-foreground">Link WhatsApp and add their number in Connect. Their chat appears here the moment they write.</p></div>
              </div>
            )}
            <TabsContent value="conversation">{detail.data && <ConversationTab detail={detail.data} />}</TabsContent>
            <TabsContent value="trace">{detail.data && <TraceTab detail={detail.data} />}</TabsContent>
            <TabsContent value="intel">{detail.data && <IntelTab detail={detail.data} />}</TabsContent>
            <TabsContent value="graph"><GraphTab onSelectSession={(id) => { setSelected(id); setTab('conversation'); }} /></TabsContent>
            <TabsContent value="takedowns"><TakedownTab sessionId={selected} /></TabsContent>
          </div>
        </Tabs>
      </section>
    </div>
  );
}