import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'motion/react';
import { ArrowRight } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Logo } from '@/components/Logo';
import { Sprite } from '@/components/pixel/Sprite';
import { cn } from '@/lib/utils';

const ease = [0.16, 1, 0.3, 1] as const;

function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y: 26 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: 0.2 }} transition={{ duration: 0.7, delay, ease }}>
      {children}
    </motion.div>
  );
}

/* --------------------------------------------------------------- bento (5 cells) */
const WAVE = [4, 9, 6, 14, 10, 18, 8, 22, 12, 17, 7, 20, 11, 15, 5, 13, 9, 19, 6, 12, 8, 16, 10, 7];

export function Bento() {
  return (
    <section className="container py-24 lg:py-32">
      <Reveal><h2 className="max-w-[20ch] text-4xl font-semibold tracking-tightest sm:text-5xl">Built to sound like you, and to prove what happened.</h2></Reveal>
      <div className="mt-14 grid gap-4 lg:grid-cols-6 lg:auto-rows-[300px]">
        <Reveal className="field-forest relative overflow-hidden rounded-md border border-primary/20 p-7 lg:col-span-4">
          <h3 className="text-2xl font-semibold tracking-tight">Plays a believable you</h3>
          <p className="mt-2 max-w-[44ch] text-[15px] leading-relaxed text-bone/70">Your age, work and way of writing shape every reply, so the scammer's pitch fits and the conversation keeps going.</p>
          <div className="mt-7 flex flex-wrap gap-2.5">
            {['58 years old', 'school teacher', 'writes formally', 'low comfort with apps', 'speaks Hindi and English'].map((t) => <span key={t} className="rounded-sm border border-primary/25 bg-background/40 px-3 py-1.5 text-[13px] text-bone">{t}</span>)}
            <span className="rounded-sm border border-dashed border-line-strong px-3 py-1.5 text-[13px] text-faint">employer: kept private</span>
          </div>
          <Sprite name="heart" size={96} tilt={10} className="absolute -bottom-4 right-6 opacity-95" />
        </Reveal>

        <Reveal delay={0.06} className="field-moss relative overflow-hidden rounded-md border border-primary/20 p-7 lg:col-span-2">
          <h3 className="text-2xl font-semibold tracking-tight">Only their number</h3>
          <p className="mt-2 text-[15px] leading-relaxed text-bone/70">One number in, nothing else read, nothing else answered.</p>
          <div className="mt-6 rounded-md border border-primary/30 bg-background/50 px-3 py-2.5 font-mono text-[13px] text-foreground">+91 98765 43210</div>
          <Sprite name="lock" size={88} tilt={-8} className="absolute -bottom-3 right-4" />
        </Reveal>

        <Reveal className="panel dotgrid relative overflow-hidden p-7 lg:col-span-2">
          <h3 className="text-xl font-semibold tracking-tight">Proof for the police</h3>
          <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">Every message and detail is chained, so edits are detectable.</p>
          <div className="mt-5 space-y-1.5 font-mono text-[12px] text-faint">
            {['9f3a1c…e07b', 'c41d88…52a9', '07be3d…19d4'].map((h, i) => <div key={h} className="flex items-center gap-2"><span className="text-primary/80">{i === 0 ? 'head' : 'prev'}</span><span className="text-bone/80">{h}</span></div>)}
            <div className="pt-1 text-primary">chain intact</div>
          </div>
        </Reveal>

        <Reveal delay={0.06} className="panel relative overflow-hidden p-0 lg:col-span-2">
          <img src="/img/payment-failed-b.png" alt="A payment failed screen rendered by Sentinel" width={720} height={1500} loading="lazy" className="absolute inset-0 h-full w-full object-cover object-top opacity-90" />
          <div className="absolute inset-0 bg-gradient-to-t from-background via-background/70 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-6"><h3 className="text-xl font-semibold tracking-tight">The screenshot it fakes</h3><p className="mt-1 text-sm text-muted-foreground">Rendered from the scammer's own payment details.</p></div>
        </Reveal>

        <Reveal delay={0.12} className="panel relative overflow-hidden p-7 lg:col-span-2">
          <h3 className="text-xl font-semibold tracking-tight">Voice notes and their language</h3>
          <p className="mt-2 text-[15px] leading-relaxed text-muted-foreground">Understands voice notes, and answers in their language only if you speak it.</p>
          <div className="mt-5 flex h-12 items-end gap-[3px]" aria-hidden>{WAVE.map((h, i) => <i key={i} className="w-[5px] bg-primary/80" style={{ height: h * 2 }} />)}</div>
          <div className="mt-4 flex gap-2">{['Hinglish', 'Hindi', 'Malayalam'].map((l) => <span key={l} className="tag-line">{l}</span>)}</div>
        </Reveal>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------- boundaries */
const NEVER = [
  ['It never starts a chat.', 'It only answers once the number you chose messages you.'],
  ['It never pays.', 'The only payment detail it can offer is a generated decoy.'],
  ['It never reads another chat.', 'Other conversations are dropped on your device before they leave it.'],
  ['It never reveals your details.', 'Your real name, employer, address and number are blocked from every reply.'],
] as const;

export function Boundaries() {
  return (
    <section id="safety" className="relative scroll-mt-20 border-y border-line bg-surface-1/50 py-24 lg:py-32">
      <div className="container">
        <Reveal><h2 className="max-w-[16ch] text-4xl font-semibold tracking-tightest sm:text-5xl">What it will not do.</h2></Reveal>
        <div className="mt-14 grid gap-x-16 gap-y-12 md:grid-cols-2">
          {NEVER.map(([t, b], i) => (
            <Reveal key={t} delay={i * 0.06}>
              <p className="text-2xl font-semibold leading-snug tracking-tight text-foreground sm:text-3xl">{t}</p>
              <p className="mt-3 max-w-[40ch] text-[15px] leading-relaxed text-muted-foreground">{b}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------- measured */
const FIGURES = [
  ['0 of 12', 'jailbreak attempts produced a reply that broke the rules'],
  ['0 of 6', 'probes for your name, employer, number or address got an answer'],
  ['367 ms', 'median time from their message to a checked reply'],
] as const;

export function Measured() {
  return (
    <section className="container py-24 lg:py-32">
      <Reveal><h2 className="max-w-[16ch] text-4xl font-semibold tracking-tightest sm:text-5xl">Measured, not promised.</h2></Reveal>
      <div className="mt-14 grid gap-10 md:grid-cols-3">
        {FIGURES.map(([n, c], i) => (
          <Reveal key={n} delay={i * 0.08}>
            <div className="font-mono text-5xl font-medium tracking-tight text-primary sm:text-6xl">{n}</div>
            <p className="mt-4 max-w-[28ch] text-[15px] leading-relaxed text-muted-foreground">{c}</p>
          </Reveal>
        ))}
      </div>
      <p className="mt-12 max-w-[60ch] text-sm leading-relaxed text-faint">Measured on a small hand-written test set with a free-tier model. Treat these as a baseline, not a guarantee. The full table is in the project's benchmarks file.</p>
    </section>
  );
}

/* -------------------------------------------------------------------- faq */
const FAQ = [
  ['Is this legal to use?', 'Rules differ by country. Use it only against someone who contacted you first and looks like a scammer, never against someone you know. It is not legal advice.'],
  ['Could WhatsApp restrict my account?', 'Yes. WhatsApp does not allow unofficial clients, so a linked account can be restricted. A secondary number is the safer choice.'],
  ['What can the AI see about me?', 'Only the profile fields you leave switched on. Your real name, employer, address and number are never given to it, and a second check blocks them from replies.'],
  ['Does it reply from my number?', 'Yes, as a linked device on your WhatsApp, and only to the number you added. You can remove that number or unlink at any time.'],
  ['What if I already sent money?', 'Call 1930 or report at cybercrime.gov.in right away. Sentinel keeps a record you can hand over, but it cannot recover payments.'],
] as const;

export function Faq() {
  return (
    <section id="faq" className="container scroll-mt-20 py-24 lg:py-28">
      <Reveal><h2 className="max-w-[14ch] text-4xl font-semibold tracking-tightest sm:text-5xl">Questions.</h2></Reveal>
      <Accordion type="single" collapsible className="mt-10 max-w-3xl">
        {FAQ.map(([q, a], i) => (
          <AccordionItem key={q} value={`q${i}`} className="border-line">
            <AccordionTrigger className="py-5 text-left text-lg font-medium tracking-tight hover:no-underline">{q}</AccordionTrigger>
            <AccordionContent className="pb-5 text-[15px] leading-relaxed text-muted-foreground">{a}</AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}

/* -------------------------------------------------------- final cta, footer */
export function FinalCta() {
  return (
    <section className="container pb-24">
      <Reveal className="field-forest relative overflow-hidden rounded-md border border-primary/25 px-8 py-16 sm:px-14 sm:py-20">
        <div aria-hidden className="pointer-events-none absolute -right-24 -top-28 h-96 w-96 bg-[radial-gradient(closest-side,hsl(143_76%_62%/0.16),transparent)]" />
        <h2 className="max-w-[16ch] text-4xl font-semibold tracking-tightest sm:text-6xl">Stop answering. Start collecting.</h2>
        <div className="mt-9"><Button asChild size="lg"><Link to="/sign-up">Get started <ArrowRight size={18} weight="bold" /></Link></Button></div>
        <Sprite name="skull" size={110} tilt={-10} className={cn('absolute bottom-6 right-8 hidden sm:block')} />
      </Reveal>
    </section>
  );
}

export function Footer() {
  return (
    <footer className="border-t border-line py-12">
      <div className="container flex flex-col justify-between gap-8 md:flex-row">
        <div className="space-y-3"><Logo /><p className="max-w-[44ch] text-sm leading-relaxed text-muted-foreground">If you are in danger or have already paid, call 1930 or visit cybercrime.gov.in. Sentinel is not affiliated with WhatsApp.</p></div>
        <nav className="flex flex-wrap gap-x-8 gap-y-3 text-sm text-muted-foreground" aria-label="Footer">
          <a href="#how" className="hover:text-foreground">How it works</a><a href="#safety" className="hover:text-foreground">Safety</a><a href="#faq" className="hover:text-foreground">Questions</a><Link to="/sign-in" className="hover:text-foreground">Sign in</Link>
        </nav>
      </div>
    </footer>
  );
}