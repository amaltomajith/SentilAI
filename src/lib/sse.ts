import type { LiveEvent } from './types';

/** Incremental Server-Sent-Events parser (fetch streams, so the admin token travels in a header, not a URL). */
export function createSseParser(onEvent: (e: LiveEvent) => void) {
  let buf = '';
  return (chunk: string) => {
    buf += chunk.replace(/\r\n/g, '\n');
    let i: number;
    while ((i = buf.indexOf('\n\n')) !== -1) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const data = block.split('\n').filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trimStart()).join('\n');
      if (!data) continue; // comments / keepalives
      try { onEvent(JSON.parse(data) as LiveEvent); } catch { /* ignore malformed frame */ }
    }
  };
}