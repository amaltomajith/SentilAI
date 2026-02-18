import { useEffect, useRef } from 'react';
import { Target, AlertTriangle, DollarSign, Clock, Shield, UserX, Skull } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';

export interface TacticalLog {
  id: string;
  timestamp: Date;
  type: 'urgency' | 'threat' | 'financial' | 'authority' | 'manipulation' | 'aggression';
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
}

interface TacticalAnalysisTerminalProps {
  logs: TacticalLog[];
}

const typeConfig: Record<TacticalLog['type'], { icon: typeof Target; label: string; color: string }> = {
  urgency: { icon: Clock, label: 'URGENCY TACTIC', color: 'text-warning' },
  threat: { icon: AlertTriangle, label: 'THREAT DETECTED', color: 'text-destructive' },
  financial: { icon: DollarSign, label: 'FINANCIAL PAYLOAD', color: 'text-secondary' },
  authority: { icon: Shield, label: 'AUTHORITY CLAIM', color: 'text-primary' },
  manipulation: { icon: UserX, label: 'MANIPULATION', color: 'text-warning' },
  aggression: { icon: Skull, label: 'AGGRESSION SPIKE', color: 'text-destructive' },
};

const severityColors: Record<TacticalLog['severity'], string> = {
  low: 'border-muted-foreground/30',
  medium: 'border-warning/50',
  high: 'border-destructive/50',
  critical: 'border-destructive animate-pulse',
};

export function TacticalAnalysisTerminal({ logs }: TacticalAnalysisTerminalProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Target className="h-4 w-4 text-secondary" />
          <h3 className="font-mono font-bold text-foreground text-sm">
            TACTICAL ANALYSIS
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-secondary animate-pulse" />
          <span className="text-xs font-mono text-muted-foreground">LIVE</span>
        </div>
      </div>

      <ScrollArea className="flex-1 pr-2" ref={scrollRef}>
        <div className="space-y-2 font-mono text-xs">
          {logs.length === 0 ? (
            <div className="text-muted-foreground/50 text-center py-8">
              <Target className="h-8 w-8 mx-auto mb-2 opacity-30" />
              <p>Awaiting threat analysis...</p>
              <p className="text-[10px] mt-1">Scammer messages will be classified here</p>
            </div>
          ) : (
            logs.map((log) => {
              const config = typeConfig[log.type];
              const Icon = config.icon;

              return (
                <div
                  key={log.id}
                  className={cn(
                    "p-2 rounded border-l-2 bg-muted/30 fade-in",
                    severityColors[log.severity]
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Icon className={cn("h-3 w-3", config.color)} />
                    <span className={cn("font-bold uppercase", config.color)}>
                      {config.label}
                    </span>
                    <span className="text-muted-foreground ml-auto">
                      {log.timestamp.toLocaleTimeString('en-US', { 
                        hour12: false, 
                        hour: '2-digit', 
                        minute: '2-digit', 
                        second: '2-digit' 
                      })}
                    </span>
                  </div>
                  <div className="text-muted-foreground pl-5">
                    &gt;&gt; {log.message}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ScrollArea>

      {/* Stats Bar */}
      <div className="mt-3 pt-3 border-t border-border/30 grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-lg font-bold font-mono text-warning">
            {logs.filter(l => l.type === 'urgency').length}
          </div>
          <div className="text-[10px] text-muted-foreground">URGENCY</div>
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-destructive">
            {logs.filter(l => l.type === 'threat' || l.type === 'aggression').length}
          </div>
          <div className="text-[10px] text-muted-foreground">THREATS</div>
        </div>
        <div>
          <div className="text-lg font-bold font-mono text-secondary">
            {logs.filter(l => l.type === 'financial').length}
          </div>
          <div className="text-[10px] text-muted-foreground">FINANCIAL</div>
        </div>
      </div>
    </div>
  );
}

// Analyzer function to classify scammer intent
export function analyzeScammerIntent(text: string): TacticalLog[] {
  const logs: TacticalLog[] = [];
  const timestamp = new Date();
  
  const patterns: { 
    regex: RegExp; 
    type: TacticalLog['type']; 
    message: string; 
    severity: TacticalLog['severity'];
  }[] = [
    // Urgency patterns
    { regex: /\b(urgent|immediately|now|today|hour|minute|hurry)\b/i, type: 'urgency', message: 'Time-pressure language detected', severity: 'medium' },
    { regex: /\b(last chance|final warning|deadline|running out)\b/i, type: 'urgency', message: 'Deadline ultimatum deployed', severity: 'high' },
    
    // Threat patterns
    { regex: /\b(police|arrest|jail|legal|court|case|FIR|warrant)\b/i, type: 'threat', message: 'Legal threat vector identified', severity: 'high' },
    { regex: /\b(block|freeze|suspend|terminate)\b/i, type: 'threat', message: 'Account threat detected', severity: 'medium' },
    { regex: /\b(raid|seize|property)\b/i, type: 'threat', message: 'Asset seizure threat', severity: 'critical' },
    
    // Financial patterns
    { regex: /₹[\d,]+|rupees?\s*[\d,]+/i, type: 'financial', message: 'Monetary demand specified', severity: 'high' },
    { regex: /\b(pay|send|transfer|upi|paytm|gpay)\b/i, type: 'financial', message: 'Payment request initiated', severity: 'medium' },
    { regex: /@[a-zA-Z]+\b/i, type: 'financial', message: 'UPI ID payload embedded', severity: 'high' },
    
    // Authority patterns
    { regex: /\b(CBI|RBI|SBI|bank|officer|manager|government)\b/i, type: 'authority', message: 'Authority impersonation attempt', severity: 'medium' },
    { regex: /\b(head office|senior|official)\b/i, type: 'authority', message: 'Hierarchical authority claimed', severity: 'low' },
    
    // Manipulation patterns
    { regex: /\b(trust|believe|help|save)\b/i, type: 'manipulation', message: 'Trust-building manipulation', severity: 'low' },
    { regex: /\b(family|children|wife|parents)\b/i, type: 'manipulation', message: 'Family leverage detected', severity: 'medium' },
    
    // Aggression patterns
    { regex: /[A-Z]{3,}/g, type: 'aggression', message: 'Aggressive capitalization', severity: 'medium' },
    { regex: /!{2,}/g, type: 'aggression', message: 'Exclamation escalation', severity: 'medium' },
    { regex: /\b(stupid|idiot|fool|dumb)\b/i, type: 'aggression', message: 'Verbal abuse deployed', severity: 'high' },
    { regex: /\?\!|\!\?/g, type: 'aggression', message: 'Hostile punctuation pattern', severity: 'low' },
  ];

  patterns.forEach((pattern, index) => {
    if (pattern.regex.test(text)) {
      logs.push({
        id: `log-${timestamp.getTime()}-${index}`,
        timestamp,
        type: pattern.type,
        message: pattern.message,
        severity: pattern.severity,
      });
    }
  });

  return logs;
}
