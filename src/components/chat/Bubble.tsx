import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/** One chat message. `scammer` sits left on a hairline surface, `agent` sits right on the forest field. Shared by the landing demo and the app. */
export function Bubble({ role, children, meta, tag, className }: { role: 'scammer' | 'agent'; children: ReactNode; meta?: ReactNode; tag?: ReactNode; className?: string }) {
  const agent = role === 'agent';
  return (
    <div className={cn('flex w-full', agent && 'justify-end', className)}>
      <div className={cn('max-w-[86%] sm:max-w-[78%]', agent && 'text-right')}>
        <div className={cn('mb-1.5 flex items-center gap-2 font-mono text-[10.5px] tracking-wide text-faint', agent && 'justify-end')}>
          <span className={cn('uppercase', agent ? 'text-primary/90' : 'text-destructive/90')}>{agent ? 'Your agent' : 'Scammer'}</span>
          {tag}
          {meta}
        </div>
        <div
          className={cn(
            'rounded-md px-3.5 py-2.5 text-left text-[14.5px] leading-relaxed',
            agent
              ? 'border border-primary/25 bg-gradient-to-br from-moss to-forest text-bone shadow-[inset_0_1px_0_hsl(150_100%_85%/0.08)]'
              : 'border border-line-strong bg-surface-2 text-bone/95',
          )}
        >
          {children}
        </div>
      </div>
    </div>
  );
}

export function Typing({ role = 'agent' }: { role?: 'scammer' | 'agent' }) {
  return (
    <div className={cn('flex', role === 'agent' && 'justify-end')} aria-label="typing">
      <div className={cn('flex items-center gap-1 rounded-md border px-3 py-2.5', role === 'agent' ? 'border-primary/25 bg-forest' : 'border-line-strong bg-surface-2')}>
        {[0, 1, 2].map((i) => <i key={i} className="h-1.5 w-1.5 rounded-[1px] bg-primary/80" style={{ animation: 'pulse-soft 1s ease-in-out infinite', animationDelay: `${i * 160}ms` }} />)}
      </div>
    </div>
  );
}