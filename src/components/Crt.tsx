import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** Fixed full-page CRT layer (scanlines, vignette, faint grain). Decorative and non-interactive. */
export function CrtOverlay() {
  return <div aria-hidden className="crt-overlay" />;
}

/** A framed local screen with its own scanlines. `title` renders as a window bar like a terminal session. */
export function CrtFrame({ title, children, className }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={cn('panel-raised overflow-hidden', className)}>
      {title && (
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <span className="font-mono text-[11px] tracking-wide text-muted-foreground">{title}</span>
          <span className="flex gap-1.5" aria-hidden><i className="h-2 w-2 rounded-[1px] bg-line-strong" /><i className="h-2 w-2 rounded-[1px] bg-line-strong" /><i className="h-2 w-2 rounded-[1px] bg-primary/70" /></span>
        </div>
      )}
      <div className="crt-screen">{children}</div>
    </div>
  );
}