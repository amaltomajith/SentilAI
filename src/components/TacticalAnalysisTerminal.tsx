/** Classifies pressure tactics in a scammer message. Display heuristics only: no decision depends on this. */
export interface TacticalLog {
  id: string;
  timestamp: Date;
  type: 'urgency' | 'threat' | 'financial' | 'authority' | 'manipulation' | 'aggression';
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
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
    { regex: /[A-Z]{3,}/, type: 'aggression', message: 'Aggressive capitalization', severity: 'medium' },
    { regex: /!{2,}/, type: 'aggression', message: 'Exclamation escalation', severity: 'medium' },
    { regex: /\b(stupid|idiot|fool|dumb)\b/i, type: 'aggression', message: 'Verbal abuse deployed', severity: 'high' },
    { regex: /\?!|!\?/, type: 'aggression', message: 'Hostile punctuation pattern', severity: 'low' },
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
