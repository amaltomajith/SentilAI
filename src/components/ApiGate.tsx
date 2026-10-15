import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { Sprite } from '@/components/pixel/Sprite';
import { backendStatus, probeHealth, reportReady, useBackendStatus, watchBackend } from '@/lib/backend';

/** Shown instead of an error while a free host boots. Continues by itself the moment the server answers. */
export function WakingScreen() {
  const [secs, setSecs] = useState(0);
  const { since } = backendStatus();
  useEffect(() => {
    const id = setInterval(() => setSecs(Math.floor((Date.now() - since) / 1000)), 500);
    return () => clearInterval(id);
  }, [since]);
  const slow = secs >= 90;
  return (
    <div className="grid min-h-[60dvh] place-items-center px-4 text-center" role="status" aria-live="polite">
      <div className="max-w-md">
        <Sprite name="eye" size={72} className="mx-auto animate-pulse" />
        <h1 className="mt-6 text-2xl font-semibold tracking-tight">Waking the server.</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
          This demo runs on free hosting that sleeps when nobody is using it. It usually takes about a minute. You do not need to do anything, the page continues by itself.
        </p>
        <div className="mx-auto mt-6 h-1 w-56 overflow-hidden rounded-sm bg-surface-3"><i className="block h-full w-1/3 animate-indeterminate bg-primary" /></div>
        <p className="mt-3 font-mono text-[12px] text-faint">{secs}s</p>
        {slow && (
          <div className="mt-5 space-y-3">
            <p className="text-sm text-warning">Taking longer than usual.</p>
            <Button variant="outline" onClick={() => { void probeHealth().then((ok) => ok && reportReady()); }}>Check again</Button>
          </div>
        )}
      </div>
    </div>
  );
}

/** Holds the app back until the API is reachable. Fast path: a healthy server never flashes the waking screen. */
export function ApiGate({ children }: { children: ReactNode }) {
  const status = useBackendStatus();
  const [late, setLate] = useState(false);
  const everReady = useRef(false);
  if (status === 'ready') everReady.current = true;

  useEffect(() => {
    if (status === 'ready') return;
    const stop = watchBackend();
    return stop;
  }, [status === 'ready']); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (status === 'ready') { setLate(false); return; }
    const id = setTimeout(() => setLate(true), 900);
    return () => clearTimeout(id);
  }, [status]);

  if (status === 'ready' || everReady.current) {
    // Same element positions in both states so the page is never remounted (nothing typed is lost); the banner only appears mid-session.
    return (
      <>
        {status === 'ready' ? null : (
          <div role="status" aria-live="polite" className="mb-5 rounded-md border border-warning/30 bg-warning/5 px-4 py-2.5 text-[13px] text-warning">Reconnecting to the server. It may take up to a minute, and your page will keep working afterwards.</div>
        )}
        {children}
      </>
    );
  }
  if (!late && status === 'checking') return null;                      // first probe is in flight; avoid a flash
  return <WakingScreen />;
}