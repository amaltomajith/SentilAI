import { useState } from 'react';
import { PaperPlaneTilt } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ManualInputProps {
  onSubmit: (message: string) => Promise<void>;
  isProcessing: boolean;
}

/** Practice composer: you type as the scammer. A command-prompt line, Enter to send, Shift+Enter for a new line. */
export function ManualInput({ onSubmit, isProcessing }: ManualInputProps) {
  const [message, setMessage] = useState('');

  const submit = () => {
    const text = message.trim();
    if (!text || isProcessing) return;
    void onSubmit(text).catch((err) => console.error('Manual submit error:', err));
    setMessage('');
  };

  return (
    <div className="border-t border-line bg-surface-1/80 p-3">
      <div className="flex items-end gap-3 rounded-md border border-line-strong bg-surface-2 px-3 py-2 focus-within:border-primary/60">
        <span className="pb-[7px] font-mono text-primary" aria-hidden>&gt;</span>
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } }}
          placeholder="Type as the scammer, for example: Your account will be blocked, send Rs 500 now"
          aria-label="Message as the scammer"
          disabled={isProcessing}
          rows={1}
          className="min-h-[34px] max-h-32 resize-none border-0 bg-transparent px-0 py-1.5 font-mono text-[13.5px] shadow-none hover:border-0 focus-visible:border-0 focus-visible:shadow-none focus-visible:outline-none"
        />
        <Button size="sm" onClick={submit} disabled={!message.trim() || isProcessing}>Send <PaperPlaneTilt size={15} weight="bold" /></Button>
      </div>
      <p className="mt-2 px-1 font-mono text-[10.5px] text-faint">Enter to send. Shift+Enter for a new line.</p>
    </div>
  );
}