import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { List, X } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Logo } from '@/components/Logo';
import { Sprite } from '@/components/pixel/Sprite';
import { useAppAuth } from '@/lib/auth';
import { wakeBackend } from '@/lib/backend';

const LINKS = [['How it works', '#how'], ['Safety', '#safety'], ['Questions', '#faq']] as const;

export function Nav() {
  const [open, setOpen] = useState(false);
  const reduce = useReducedMotion();
  const { signedIn } = useAppAuth();
  useEffect(() => { wakeBackend(); }, []);          // start the free host now, while the visitor reads the page
  const cta = signedIn ? { to: '/app', label: 'Open app' } : { to: '/sign-up', label: 'Get started' };
  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-background/75 backdrop-blur-md">
      <div className="container flex h-16 items-center justify-between">
        <Logo />
        <nav className="hidden items-center gap-8 md:flex" aria-label="Primary">
          {LINKS.map(([l, h]) => <a key={h} href={h} className="text-[14px] text-muted-foreground transition-colors hover:text-foreground">{l}</a>)}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {!signedIn && <Button asChild variant="ghost" size="sm"><Link to="/sign-in">Sign in</Link></Button>}
          <Button asChild size="sm"><Link to={cta.to}>{cta.label}</Link></Button>
        </div>
        <button className="grid h-10 w-10 place-items-center rounded-md border border-line-strong md:hidden" onClick={() => setOpen(true)} aria-label="Open menu"><List size={20} /></button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-50 grid place-items-start bg-background/80 p-3 backdrop-blur-sm md:hidden" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setOpen(false)}>
            <motion.div className="panel-raised w-full overflow-hidden" initial={reduce ? false : { y: -24, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -24, opacity: 0 }} transition={{ type: 'spring', stiffness: 260, damping: 28 }} onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between border-b border-line px-4 py-3"><Logo size={22} /><button onClick={() => setOpen(false)} aria-label="Close menu" className="grid h-9 w-9 place-items-center rounded-md border border-line-strong"><X size={18} /></button></div>
              <div className="grid grid-cols-[1fr_auto] gap-4 p-5">
                <ul className="space-y-1">
                  {LINKS.map(([l, h]) => <li key={h}><a href={h} onClick={() => setOpen(false)} className="block py-2 text-3xl font-semibold tracking-tight text-foreground">{l}</a></li>)}
                  {!signedIn && <li><Link to="/sign-in" className="block py-2 text-3xl font-semibold tracking-tight text-muted-foreground">Sign in</Link></li>}
                </ul>
                <div className="field-moss grid h-28 w-28 place-items-center rounded-md border border-primary/25 sm:h-36 sm:w-36"><Sprite name="eye" size={72} /></div>
              </div>
              <div className="border-t border-line p-4"><Button asChild className="w-full" size="lg"><Link to={cta.to}>{cta.label}</Link></Button></div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}