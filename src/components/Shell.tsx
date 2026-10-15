import { NavLink, Navigate, Outlet } from 'react-router-dom';
import { ApiGate } from '@/components/ApiGate';
import { AppHeader, STEPS } from '@/components/AppHeader';
import { Sprite } from '@/components/pixel/Sprite';
import { useAppAuth } from '@/lib/auth';
import { useLiveSync, useMe, useProfile } from '@/lib/hooks';
import { cn } from '@/lib/utils';

export function Shell() {
  const auth = useAppAuth();
  const live = useLiveSync(auth.signedIn);
  if (!auth.loaded) return <div className="grid min-h-screen place-items-center"><Sprite name="eye" size={56} className="animate-pulse" /></div>;
  if (!auth.signedIn) return <Navigate to="/sign-in" replace />;
  return (
    <div className="min-h-screen pb-20 md:pb-0">
      <AppHeader live={live} />
      <main className="container py-8"><ApiGate><Outlet /></ApiGate></main>
      <footer className="border-t border-line py-5 text-center font-mono text-[11px] text-faint">Use only against people who contacted you first and look like scammers.</footer>
      <nav className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-line bg-background/90 backdrop-blur-md md:hidden" aria-label="Steps">
        {STEPS.map(([to, label], i) => (
          <NavLink key={to} to={to} className={({ isActive }) => cn('flex flex-col items-center gap-1 py-3 text-[11px]', isActive ? 'text-primary' : 'text-muted-foreground')}>
            <span className="font-pixel text-[11px]">{`0${i + 1}`}</span>{label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

/** First landing after sign-in: finish the profile first, otherwise go to the live view. */
export function Home() {
  const me = useMe();
  const prof = useProfile();
  if (me.isLoading || prof.isLoading) return <div className="grid place-items-center py-32"><Sprite name="eye" size={56} className="animate-pulse" /></div>;
  return <Navigate to={me.data?.consented && prof.data?.complete ? '/live' : '/onboarding'} replace />;
}