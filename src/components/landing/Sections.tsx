import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { motion, useInView, useReducedMotion } from 'motion/react';
import { QRCodeSVG } from 'qrcode.react';
import { ArrowRight } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { CrtFrame } from '@/components/Crt';
import { Sprite } from '@/components/pixel/Sprite';
import { Bubble } from '@/components/chat/Bubble';
import { ScriptedChat } from '@/components/landing/ScriptedChat';
import { cn } from '@/lib/utils';

const ease = [0.16, 1, 0.3, 1] as const;

function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 26 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.25 }} transition={{ duration: 0.7, delay, ease }}>
      {children}
    </motion.div>
  );
}

/* ---------------------------------------------------------------- hero */
export function Hero() {
  const reduce = useReducedMotion();
  return (
    <section className="relative isolate overflow-hidden">
      <div aria-hidden className="pointer-events-none absolute -right-40 -top-40 -z-10 h-[700px] w-[700px] bg-[radial-gradient(closest-side,hsl(151_48%_16%/0.55),transparent)]" />
      <div className="container grid min-h-[calc(100dvh-4rem)] items-center gap-12 pb-16 pt-12 lg:grid-cols-[1.05fr_0.95fr] lg:pt-16">
        <div>
          <motion.h1 initial={reduce ? false : { opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, ease }} className="text-[2.75rem] font-semibold leading-[0.98] tracking-tightest text-foreground sm:text-6xl lg:text-[4.6rem]">
            Let them chase<br /><span className="text-primary">a ghost.</span>
          </motion.h1>
          <motion.p initial={reduce ? false : { opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.12, ease }} className="mt-6 max-w-[46ch] text-lg leading-relaxed text-muted-foreground">
            Link your WhatsApp, name the scammer's number, and your agent answers them while you keep the proof.
          </motion.p>
          <motion.div initial={reduce ? false : { opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.24, ease }} className="mt-9 flex flex-wrap items-center gap-3">
            <Button asChild size="lg"><Link to="/sign-up">Get started <ArrowRight size={18} weight="bold" /></Link></Button>
            <Button asChild size="lg" variant="outline"><a href="#how">See how it works</a></Button>
          </motion.div>
        </div>

        <motion.div initial={reduce ? false : { opacity: 0, y: 40, rotate: 1.5 }} animate={{ opacity: 1, y: 0, rotate: 0 }} transition={{ duration: 1, delay: 0.2, ease }} className="relative mx-auto w-full max-w-[520px]">
          <Sprite name="shield" size={84} tilt={-12} className="absolute -left-12 top-32 z-10 animate-float-y [--r:-12deg]" />
          <Sprite name="eye" size={72} tilt={8} className="absolute -bottom-9 -right-6 z-10 animate-float-y [--r:8deg] [animation-delay:-3s]" />
          <Sprite name="bolt" size={52} tilt={14} className="absolute -right-10 top-20 z-10 hidden animate-float-y [--r:14deg] [animation-delay:-5s] sm:block" />
          <CrtFrame title="whatsapp / +91 98xxx xxx10" className="shadow-[0_40px_90px_-30px_hsl(143_70%_40%/0.35)]">
            <ScriptedChat />
          </CrtFrame>
          <p className="mt-3 text-center font-mono text-[11px] text-faint">Example conversation, played from our real chat components.</p>
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------- how it works */
const STEPS = [
  { key: 'about', title: 'Tell it who you are', body: 'Name, age, what you do, how you write. Switch off anything the agent should not mention. Private details never reach the AI.' },
  { key: 'practice', title: 'Rehearse on a sample scam', body: 'Watch a simulated scammer pitch your agent. Check the replies sound like you before anything goes live.' },
  { key: 'connect', title: 'Link WhatsApp, name one number', body: 'Scan a code, paste the scammer\'s number. Every other chat on your phone is ignored.' },
  { key: 'live', title: 'Watch it work, keep the proof', body: 'Their messages and your agent\'s replies appear live. Payment details are logged in a tamper-evident record.' },
] as const;

function StepPreview({ k }: { k: (typeof STEPS)[number]['key'] }) {
  if (k === 'about') {
    return (
      <div className="panel-raised space-y-4 p-6">
        {[['Name the agent uses', 'Anita'], ['Age', '58'], ['What you do', 'school teacher']].map(([l, v]) => (
          <div key={l}><div className="label-mono mb-1.5">{l}</div><div className="rounded-md border border-line-strong bg-surface-2 px-3 py-2.5 text-sm text-foreground">{v}</div></div>
        ))}
        <div className="space-y-2.5 border-t border-line pt-4">
          {[['The agent may mention my age', true], ['The agent may mention my city', false], ['Keep my employer private', true]].map(([l, on]) => (
            <label key={String(l)} className="flex items-center justify-between text-sm text-muted-foreground"><span>{l}</span><Switch checked={on as boolean} aria-label={String(l)} className="pointer-events-none" /></label>
          ))}
        </div>
      </div>
    );
  }
  if (k === 'practice') {
    return (
      <CrtFrame title="why it replied that way">
        <div className="space-y-5 p-6 font-mono text-[13px]">
          {[['scam type', 'fake KYC alert'], ['stage', 'payment pushed'], ['pressure', 'high'], ['their language', 'English'], ['chosen tactic', 'say the app failed, ask for a bank transfer']].map(([l, v]) => (
            <div key={l} className="flex items-baseline justify-between gap-6 border-b border-line pb-3 last:border-0"><span className="text-faint">{l}</span><span className={cn('text-right', l === 'chosen tactic' ? 'text-primary' : 'text-foreground')}>{v}</span></div>
          ))}
          <p className="text-[12px] leading-relaxed text-faint">Next to each reply you see what was detected and which tactic was picked, so nothing the agent does is a black box.</p>
        </div>
      </CrtFrame>
    );
  }
  if (k === 'connect') {
    return (
      <div className="panel-raised grid gap-6 p-6 sm:grid-cols-[auto_1fr] sm:items-center">
        <div className="relative mx-auto w-fit rounded-md border border-primary/30 bg-bone p-3">
          <QRCodeSVG value="sentinel-demo-code-not-a-real-link" size={150} bgColor="transparent" fgColor="#06100A" />
          {(['left-0 top-0 border-l-2 border-t-2', 'right-0 top-0 border-r-2 border-t-2', 'bottom-0 left-0 border-b-2 border-l-2', 'bottom-0 right-0 border-b-2 border-r-2'] as const).map((c) => <i key={c} className={cn('absolute h-4 w-4 border-primary', c)} />)}
          <i className="absolute inset-x-2 top-0 h-px animate-sweep bg-primary shadow-[0_0_10px_hsl(143_76%_62%)]" />
        </div>
        <div className="space-y-3">
          <div className="label-mono">Engaging</div>
          <div className="flex items-center justify-between rounded-md border border-primary/30 bg-forest px-3 py-2.5 font-mono text-sm text-foreground"><span>+91 98765 43210</span><span className="tag-pixel">only this</span></div>
          <p className="text-sm text-muted-foreground">Everything else in your WhatsApp stays on your phone.</p>
        </div>
      </div>
    );
  }
  return (
    <CrtFrame title="live / +91 98765 43210">
      <div className="space-y-4 p-5">
        <Bubble role="scammer" meta={<span>10:43</span>}>Why is it not paying? Send me a screenshot now.</Bubble>
        <Bubble role="agent" tag={<span className="tag-line">gate pass</span>} meta={<span>10:43</span>}>
          I tried again sir, it shows an error. Here is the screen.
          <img src="/img/payment-failed-a.png" alt="Payment failed screen the agent sent" width={720} height={1500} loading="lazy" className="mt-3 max-h-64 w-auto rounded-sm border border-line-strong" />
        </Bubble>
      </div>
    </CrtFrame>
  );
}

export function HowItWorks() {
  const [active, setActive] = useState(0);
  return (
    <section id="how" className="container scroll-mt-20 py-24 lg:py-32">
      <Reveal><h2 className="max-w-[18ch] text-4xl font-semibold tracking-tightest sm:text-5xl">Four steps, one number.</h2></Reveal>
      <div className="mt-14 grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:gap-20">
        <ol className="space-y-2 lg:sticky lg:top-28 lg:self-start">
          {STEPS.map((s, i) => (
            <li key={s.key} className={cn('rounded-md border px-5 py-4 transition-colors duration-300', i === active ? 'border-primary/35 bg-forest/60' : 'border-transparent')}>
              <div className="flex items-baseline gap-4">
                <span className={cn('font-pixel text-[13px]', i === active ? 'text-primary' : 'text-faint')}>{`0${i + 1}`}</span>
                <div>
                  <h3 className={cn('text-xl font-semibold tracking-tight transition-colors', i === active ? 'text-foreground' : 'text-muted-foreground')}>{s.title}</h3>
                  <div className={cn('grid transition-[grid-template-rows,opacity] duration-300 ease-out', i === active ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0')}>
                    <p className="mt-1.5 max-w-[42ch] overflow-hidden text-[15px] leading-relaxed text-muted-foreground">{s.body}</p>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ol>
        <div className="space-y-6 lg:space-y-[24vh]">
          {STEPS.map((s, i) => <StepPanel key={s.key} i={i} onActive={setActive}><StepPreview k={s.key} /><p className="mt-4 text-[15px] leading-relaxed text-muted-foreground lg:hidden">{s.body}</p></StepPanel>)}
        </div>
      </div>
    </section>
  );
}

function StepPanel({ i, onActive, children }: { i: number; onActive: (i: number) => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { amount: 0.55 });
  useEffect(() => { if (inView) onActive(i); }, [inView, i, onActive]);
  return <div ref={ref}>{children}</div>;
}