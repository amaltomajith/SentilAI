import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { AuthenticateWithRedirectCallback, ClerkProvider, SignIn, SignUp, useAuth, useUser } from '@clerk/clerk-react';
import { Shield } from '@phosphor-icons/react';
import { Logo } from '@/components/Logo';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { setTokenProvider } from '@/lib/api';
import { wakeBackend } from '@/lib/backend';

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
const DEV = import.meta.env.VITE_DEV_AUTH === '1';
/** clerk = real sign-up/sign-in. dev = local testing only (backend must run with DEV_AUTH=1). none = not configured yet. */
export const authMode: 'clerk' | 'dev' | 'none' = DEV ? 'dev' : CLERK_KEY ? 'clerk' : 'none';

export interface AuthState { loaded: boolean; signedIn: boolean; label: string; signOut: () => void; devSignIn: (name: string) => void }
const noop = () => undefined;
const Ctx = createContext<AuthState>({ loaded: false, signedIn: false, label: '', signOut: noop, devSignIn: noop });
export const useAppAuth = () => useContext(Ctx);

function ClerkBridge({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const { user } = useUser();
  setTokenProvider(async () => (isSignedIn ? getToken() : null));
  const value = useMemo<AuthState>(() => ({
    loaded: isLoaded, signedIn: !!isSignedIn, label: user?.primaryEmailAddress?.emailAddress ?? user?.firstName ?? '',
    signOut: () => { void signOut(); }, devSignIn: noop,
  }), [isLoaded, isSignedIn, user, signOut]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

const DEV_KEY = 'sentinel_dev_user';
function DevProvider({ children }: { children: ReactNode }) {
  const [name, setName] = useState<string>(() => { try { return localStorage.getItem(DEV_KEY) ?? ''; } catch { return ''; } });
  setTokenProvider(async () => (name ? `dev:${name}` : null));
  const value = useMemo<AuthState>(() => ({
    loaded: true, signedIn: !!name, label: name ? `${name} (dev)` : '',
    signOut: () => { try { localStorage.removeItem(DEV_KEY); } catch { /* ignore */ } setName(''); },
    devSignIn: (n) => { try { localStorage.setItem(DEV_KEY, n); } catch { /* ignore */ } setName(n); },
  }), [name]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  if (authMode === 'clerk') {
    return (
      <ClerkProvider publishableKey={CLERK_KEY!} routerPush={(to) => navigate(to)} routerReplace={(to) => navigate(to, { replace: true })}
                     afterSignOutUrl="/" appearance={{
        variables: { colorPrimary: '#5BE98D', colorBackground: '#0B120E', colorText: '#E7EFE9', colorTextSecondary: '#8FA597', colorInputBackground: '#101A14', colorInputText: '#E7EFE9', colorNeutral: '#E7EFE9', borderRadius: '4px', fontFamily: '"Geist Variable", system-ui, sans-serif' },
        elements: { card: 'border border-[#1b2a22] shadow-[0_30px_80px_-30px_rgba(0,0,0,0.8)]', formButtonPrimary: 'text-[#04120A] font-medium', footerActionLink: 'text-[#5BE98D]' },
      }}>
        <ClerkBridge>{children}</ClerkBridge>
      </ClerkProvider>
    );
  }
  if (authMode === 'dev') return <DevProvider>{children}</DevProvider>;
  return <Ctx.Provider value={{ loaded: true, signedIn: false, label: '', signOut: noop, devSignIn: noop }}>{children}</Ctx.Provider>;
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="relative grid min-h-[100dvh] place-items-center overflow-hidden px-4 py-12">
      <div aria-hidden className="pointer-events-none absolute -right-32 -top-32 h-[620px] w-[620px] bg-[radial-gradient(closest-side,hsl(151_48%_16%/0.5),transparent)]" />
      <div className="relative w-full max-w-md space-y-6">
        <div className="flex justify-center"><Logo size={30} /></div>
        {children}
      </div>
    </div>
  );
}

export function SignInPage({ mode }: { mode: 'in' | 'up' }) {
  const [name, setName] = useState('');
  const { devSignIn, signedIn } = useAppAuth();
  useEffect(() => { wakeBackend(); }, []);
  if (signedIn) return <Navigate to="/app" replace />;
  if (authMode === 'clerk') {
    return <Frame><div className="flex justify-center">{mode === 'in'
      ? <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" fallbackRedirectUrl="/app" />
      : <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" fallbackRedirectUrl="/app" />}</div></Frame>;
  }
  if (authMode === 'dev') {
    return (
      <Frame>
        <Card className="p-6 space-y-3 bg-card/80">
          <p className="text-sm leading-relaxed text-warning">Dev sign-in (no Clerk configured). Local testing only: the backend must run with DEV_AUTH=1.</p>
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); const n = name.trim().replace(/[^A-Za-z0-9_-]/g, '').slice(0, 40); if (n) devSignIn(n); }}>
            <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="any test name, e.g. alice" className="font-mono" />
            <Button type="submit" className="w-full">Continue</Button>
          </form>
        </Card>
      </Frame>
    );
  }
  return (
    <Frame>
      <Card className="p-6 space-y-3 bg-card/80">
        <p className="text-sm font-mono text-warning">Sign-in is not configured.</p>
        <p className="text-xs font-mono text-muted-foreground">Create a free Clerk application, then put its publishable key in <code>.env.local</code> as <code>VITE_CLERK_PUBLISHABLE_KEY</code>, and set <code>CLERK_ISSUER</code> in <code>backend/.env</code> (see README, "Authentication").</p>
      </Card>
    </Frame>
  );
}
/** Finishes a Google/OAuth round trip. A new user who still owes a required field goes to the "continue" step instead of spinning forever. */
export function SsoCallback() {
  return (
    <Frame>
      <div className="flex justify-center">
        <AuthenticateWithRedirectCallback signInFallbackRedirectUrl="/app" signUpFallbackRedirectUrl="/app" continueSignUpUrl="/sign-up/continue" signInUrl="/sign-in" signUpUrl="/sign-up" />
      </div>
    </Frame>
  );
}
