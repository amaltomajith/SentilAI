import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { Bubble, Typing } from '@/components/chat/Bubble';

const SCRIPT = [
  { role: 'scammer', text: 'Dear customer, your SBI KYC has expired. Pay Rs 500 now or the account will be blocked.' },
  { role: 'agent', text: 'Oh no, I am very worried. Where should I send it? My app keeps failing.' },
  { role: 'scammer', text: 'Send to refund.dept@ybl immediately.' },
  { role: 'agent', text: 'It says daily limit exceeded. Can I do a bank transfer? Please share the account number.' },
  { role: 'scammer', text: 'A/C 50100123456789, IFSC HDFC0001234. Do it now.' },
] as const;

/** The real chat components playing a scripted exchange. Static (fully visible) under reduced motion. */
export function ScriptedChat({ compact = false }: { compact?: boolean }) {
  const reduce = useReducedMotion();
  const [n, setN] = useState(reduce ? SCRIPT.length : 0);
  const timer = useRef<number>();

  useEffect(() => {
    if (reduce) { setN(SCRIPT.length); return; }
    let i = 0, stopped = false;
    const run = () => {
      if (stopped) return;
      const delay = i === 0 ? 900 : i < SCRIPT.length ? (SCRIPT[i].role === 'agent' ? 2300 : 1700) : 4500;   // hold the finished chat, then replay
      timer.current = window.setTimeout(() => { i = i >= SCRIPT.length ? 0 : i + 1; setN(i); run(); }, delay);
    };
    run();
    return () => { stopped = true; window.clearTimeout(timer.current); };
  }, [reduce]);

  const next = SCRIPT[n];
  return (
    <div className={compact ? 'min-h-[300px] space-y-3 p-4' : 'min-h-[430px] space-y-4 p-5'} role="img" aria-label="Example conversation: a scammer asks for money and the agent keeps them talking until they share account details">
      <AnimatePresence initial={false}>
        {SCRIPT.slice(0, n).map((m, i) => (
          <motion.div key={i} initial={reduce ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}>
            <Bubble role={m.role} meta={<span>{`10:${14 + i}`}</span>}>{m.text}</Bubble>
          </motion.div>
        ))}
      </AnimatePresence>
      {!reduce && next && n < SCRIPT.length && <Typing role={next.role} />}
      {n >= SCRIPT.length && (
        <motion.div initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 border-t border-line pt-3 font-mono text-[11px] text-muted-foreground">
          <span className="tag-pixel">logged</span> 2 payment details captured as evidence
        </motion.div>
      )}
    </div>
  );
}