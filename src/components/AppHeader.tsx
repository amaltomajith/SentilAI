import { NavLink } from 'react-router-dom';
import { DeviceMobile } from '@phosphor-icons/react';
import { Button } from '@/components/ui/button';
import { Logo } from '@/components/Logo';
import { useAppAuth } from '@/lib/auth';
import { useWhatsApp } from '@/lib/hooks';
import { cn } from '@/lib/utils';

export const STEPS = [['/onboarding', 'About you'], ['/practice', 'Practice'], ['/connect', 'Connect'], ['/live', 'Live']] as const;

export function AppHeader({ live }: { live: boolean }) {
  const auth = useAppAuth();
  const wa = useWhatsApp();
  const linked = wa.data?.state === 'open';
  return (
    <header className="sticky top-0 z-40 border-b border-line/80 bg-background/80 backdrop-blur-md">
      <div className="container flex h-16 items-center justify-between gap-4">
        <Logo to="/app" />
        <nav className="hidden items-center gap-1 md:flex" aria-label="Steps">
          {STEPS.map(([to, label], i) => (
            <NavLink key={to} to={to} className={({ isActive }) => cn('group flex items-center gap-2 rounded-md px-3 py-2 text-[13.5px] transition-colors', isActive ? 'bg-surface-2 text-foreground' : 'text-muted-foreground hover:text-foreground')}>
              {({ isActive }) => (<><span className={cn('font-pixel text-[11px]', isActive ? 'text-primary' : 'text-faint group-hover:text-muted-foreground')}>{`0${i + 1}`}</span>{label}</>)}
            </NavLink>
          ))}
        </nav>
        <div className="flex items-center gap-2.5">
          <span className={cn('hidden items-center gap-1.5 rounded-sm border px-2 py-1 font-mono text-[11px] sm:inline-flex', linked ? 'border-primary/40 text-primary' : 'border-line-strong text-muted-foreground')} title={live ? 'Live updates connected' : 'Live updates offline'}>
            <DeviceMobile size={13} />{linked ? `+${wa.data?.me ?? 'linked'}` : 'not linked'}
          </span>
          {auth.label && <span className="hidden max-w-[160px] truncate font-mono text-[11px] text-faint lg:inline">{auth.label}</span>}
          <Button size="sm" variant="ghost" onClick={auth.signOut}>Sign out</Button>
        </div>
      </div>
    </header>
  );
}