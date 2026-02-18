import { Database, AlertCircle, Copy, Check, Link, Phone, CreditCard, Mail, Globe, Building } from 'lucide-react';
import { useState } from 'react';
import type { ExtractedIntel } from '@/lib/scamAnalyzer';
import { Button } from '@/components/ui/button';

interface IntelTableProps {
  intel: ExtractedIntel[];
}

const TYPE_ICONS: Record<ExtractedIntel['type'], React.ElementType> = {
  'UPI ID': CreditCard,
  'Phone Number': Phone,
  'URL': Link,
  'Email': Mail,
  'Bank Account': CreditCard,
  'Phishing URL': Globe,
  'IFSC Code': Building,
};

export function IntelTable({ intel }: IntelTableProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  
  const copyValue = (value: string, index: number) => {
    navigator.clipboard.writeText(value);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };
  
  const getRiskBadge = (risk: ExtractedIntel['risk']) => {
    const styles = {
      Critical: 'bg-destructive/30 text-destructive border-destructive/50 animate-pulse',
      High: 'bg-destructive/20 text-destructive border-destructive/30',
      Medium: 'bg-warning/20 text-warning border-warning/30',
      Low: 'bg-success/20 text-success border-success/30',
    };
    return styles[risk];
  };
  
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-2 w-2 rounded-full bg-warning animate-pulse" />
        <h3 className="text-sm font-semibold text-muted-foreground font-mono uppercase tracking-wider">
          Extracted Intelligence
        </h3>
      </div>
      
      {intel.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 bg-muted/20 rounded-lg border border-border/30">
          <Database className="h-10 w-10 text-muted-foreground/50 mb-3" />
          <p className="text-sm text-muted-foreground font-mono">No identifiable data extracted</p>
          <p className="text-xs text-muted-foreground/50 mt-1">Scammer was careful with their message</p>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <div className="space-y-2">
            {intel.map((item, index) => {
              const Icon = TYPE_ICONS[item.type];
              return (
                <div
                  key={`${item.type}-${item.value}`}
                  className="bg-muted/30 border border-border/50 rounded-lg p-3 hover:border-primary/30 transition-colors animate-fade-in"
                  style={{ animationDelay: `${index * 100}ms` }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <div className="flex-shrink-0 h-8 w-8 rounded bg-muted flex items-center justify-center">
                        <Icon className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-muted-foreground font-mono mb-0.5">{item.type}</div>
                        <div className="text-sm font-mono text-foreground truncate">{item.value}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className={`px-2 py-0.5 text-xs font-mono border rounded ${getRiskBadge(item.risk)}`}>
                        {item.risk}
                      </span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => copyValue(item.value, index)}
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                      >
                        {copiedIndex === index ? (
                          <Check className="h-3 w-3 text-success" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          
          {/* Summary */}
          <div className="mt-4 pt-3 border-t border-border/30">
            <div className="flex items-center gap-2 text-xs font-mono text-warning">
              <AlertCircle className="h-3 w-3" />
              <span>{intel.length} potential identifier{intel.length !== 1 ? 's' : ''} flagged for investigation</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
