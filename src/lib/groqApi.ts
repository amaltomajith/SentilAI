// Groq API integration via backend
// All AI calls (scammer via SambaNova, defender via Groq) go through the backend
// Supports both Supabase edge functions and Vercel API routes
import { supabase } from '@/integrations/supabase/client';

// Detect if running on Vercel (no Supabase edge functions available)
const IS_VERCEL = Boolean(
  import.meta.env.VITE_VERCEL === '1' ||
  import.meta.env.VITE_USE_VERCEL_API === '1' ||
  (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app'))
);

export interface GroqMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface GroqResponse {
  content: string;
  shouldConclude?: boolean;
  exchangeCount?: number;
}

export interface DetectResult {
  verdict: 'SCAM' | 'SAFE' | 'UNKNOWN';
  confidence: number;
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function isRateLimitError(err: unknown, data?: any) {
  const msg = (err instanceof Error ? err.message : String(err || '')).toLowerCase();
  const dataErr = String(data?.error || '').toLowerCase();
  return (
    msg.includes('429') ||
    msg.includes('rate limit') ||
    dataErr.includes('rate limit') ||
    dataErr.includes('429')
  );
}

async function invokeSupabase(body: Record<string, unknown>): Promise<{ data: any; error: any }> {
  return supabase.functions.invoke('groq-chat', { body });
}

async function invokeVercel(body: Record<string, unknown>): Promise<{ data: any; error: any }> {
  try {
    const resp = await fetch('/api/groq-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      return { data: errData, error: new Error(errData?.error || `HTTP ${resp.status}`) };
    }
    const data = await resp.json();
    return { data, error: null };
  } catch (err) {
    return { data: null, error: err };
  }
}

async function invokeWithBackoff<T>(
  body: Record<string, unknown>,
  opts: { retries?: number; baseDelayMs?: number } = {}
): Promise<T> {
  const retries = opts.retries ?? 4;
  const baseDelayMs = opts.baseDelayMs ?? 1200;
  const invoke = IS_VERCEL ? invokeVercel : invokeSupabase;

  let lastErr: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const { data, error } = await invoke(body);

    if (!error && !data?.error) return data as T;

    lastErr = error ?? new Error(data?.error || 'Unknown function error');

    if (attempt < retries && isRateLimitError(lastErr, data)) {
      const delay = baseDelayMs * Math.pow(2, attempt) + Math.floor(Math.random() * 250);
      console.warn(`Rate limited (attempt ${attempt + 1}/${retries + 1}); retrying in ${delay}ms`);
      await sleep(delay);
      continue;
    }

    throw lastErr instanceof Error ? lastErr : new Error(String(lastErr));
  }

  throw lastErr instanceof Error ? lastErr : new Error('Failed to invoke backend function');
}

// Detect if a message is a scam - returns verdict + confidence
export async function detectScam(message: string): Promise<DetectResult> {
  try {
    const data = await invokeWithBackoff<{ content?: string }>({
      type: 'detect',
      scammerMessage: message,
    });
    const raw = (data?.content || '').trim();
    console.log('Scam detection raw result:', raw);

    // Try to parse JSON response
    try {
      const parsed = JSON.parse(raw);
      return {
        verdict: parsed.verdict === 'SAFE' ? 'SAFE' : 'SCAM',
        confidence: typeof parsed.confidence === 'number' ? parsed.confidence : 75,
      };
    } catch {
      // Fallback: just check for SCAM/SAFE keyword
      const upper = raw.toUpperCase();
      if (upper.includes('SAFE')) return { verdict: 'SAFE', confidence: 60 };
      if (upper.includes('SCAM')) return { verdict: 'SCAM', confidence: 80 };
      return { verdict: 'UNKNOWN', confidence: 50 };
    }
  } catch (error) {
    console.error('Scam detection error:', error);
    return { verdict: 'UNKNOWN', confidence: 50 };
  }
}

// Generate scammer message via edge function (now uses SambaNova on backend)
export async function generateScammerMessage(
  conversationHistory: string[] = [],
  exchangeCount: number = 0,
  scenarioType?: string,
  scenarioMessage?: string,
): Promise<GroqResponse> {
  const data = await invokeWithBackoff<any>({
    type: 'scammer',
    conversationHistory,
    exchangeCount,
    scenarioType,
    scenarioMessage,
  });

  return {
    content: data?.content || '',
    shouldConclude: data?.shouldConclude || false,
    exchangeCount: data?.exchangeCount || 0,
  };
}

// Generate Ramesh's response via edge function
export async function generateRameshResponse(
  scammerMessage: string,
  conversationHistory: string[] = [],
  exchangeCount: number = 0
): Promise<GroqResponse> {
  const data = await invokeWithBackoff<any>({
    type: 'ramesh',
    scammerMessage,
    conversationHistory,
    exchangeCount,
  });

  return {
    content: data?.content || '',
    shouldConclude: data?.shouldConclude || false,
    exchangeCount: data?.exchangeCount || 0,
  };
}

// Generate conclusion message
export async function generateConclusion(): Promise<string> {
  try {
    const data = await invokeWithBackoff<{ content?: string }>({ type: 'conclude' }, { retries: 2 });
    return data?.content || "Thank you for wasting your time with me. I knew it was a scam all along! 🙏";
  } catch (error) {
    console.error('Conclusion error:', error);
    return "Thank you for wasting your time with me. I knew it was a scam all along! 🙏";
  }
}
