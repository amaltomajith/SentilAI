import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ShieldAlert, ShieldCheck, Clock, MessageSquare, Brain, Download } from 'lucide-react';
import type { Message } from '@/components/ConversationLoop';
import type { ExtractedIntel } from '@/lib/scamAnalyzer';
import { generateForensicReport } from '@/lib/forensicReportGenerator';

interface SummaryPopupProps {
  open: boolean;
  onClose: () => void;
  messages: Message[];
  extractedIntel: ExtractedIntel[];
  exchangeCount: number;
  scenarioType?: string;
}

export function SummaryPopup({
  open,
  onClose,
  messages,
  extractedIntel,
  exchangeCount,
  scenarioType,
}: SummaryPopupProps) {
  const scammerMessages = messages.filter((m) => m.sender === 'scammer');
  const agentMessages = messages.filter((m) => m.sender === 'agent');
  const confirmedScams = scammerMessages.filter((m) => m.status === 'scam');
  const safeMessages = scammerMessages.filter((m) => m.status === 'safe');

  const avgConfidence =
    confirmedScams.length > 0
      ? Math.round(
          confirmedScams.reduce((sum, m) => sum + (m.confidence || 0), 0) /
            confirmedScams.length
        )
      : 0;

  const isThreat = confirmedScams.length > 0;

  const handleDownloadReport = () => {
    generateForensicReport({
      messages,
      extractedIntel,
      exchangeCount,
      scenarioType,
      confidence: avgConfidence > 0 ? avgConfidence : 0,
      isThreat,
    });
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="bg-card border-border max-w-md">
        <DialogHeader>
          <DialogTitle className="font-mono text-primary flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Session Summary
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Stats grid */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
              <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground mb-1">
                <MessageSquare className="h-3 w-3" />
                Exchanges
              </div>
              <div className="text-2xl font-bold text-foreground font-mono">{exchangeCount}</div>
            </div>
            <div className="bg-muted/30 rounded-lg p-3 border border-border/50">
              <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground mb-1">
                <Clock className="h-3 w-3" />
                Messages
              </div>
              <div className="text-2xl font-bold text-foreground font-mono">{messages.length}</div>
            </div>
          </div>

          {/* Detection breakdown */}
          <div className="bg-muted/20 rounded-lg p-3 border border-border/50 space-y-2">
            <div className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
              Detection Breakdown
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-destructive" />
                <span className="text-sm font-mono">Scam Detected</span>
              </div>
              <Badge variant="destructive" className="font-mono">
                {confirmedScams.length}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
                <span className="text-sm font-mono">False Positive</span>
              </div>
              <Badge className="bg-emerald-500/20 text-emerald-500 border-emerald-500/30 font-mono">
                {safeMessages.length}
              </Badge>
            </div>
            {avgConfidence > 0 && (
              <div className="text-xs font-mono text-muted-foreground pt-1 border-t border-border/30">
                Avg. Scam Confidence: <span className="text-destructive font-bold">{avgConfidence}%</span>
              </div>
            )}
          </div>

          {/* Scenario */}
          {scenarioType && (
            <div className="text-xs font-mono text-muted-foreground">
              Active Scenario: <span className="text-secondary">{scenarioType}</span>
            </div>
          )}

          {/* Intel extracted */}
          {extractedIntel.length > 0 && (
            <div className="bg-muted/20 rounded-lg p-3 border border-border/50">
              <div className="text-xs font-mono text-muted-foreground uppercase tracking-wider mb-2">
                Intel Extracted ({extractedIntel.length})
              </div>
              <div className="space-y-1">
                {extractedIntel.slice(0, 5).map((intel, i) => (
                  <div key={i} className="flex items-center justify-between text-xs font-mono">
                    <span className="text-muted-foreground">{intel.type}</span>
                    <span className="text-primary truncate max-w-[180px]">{intel.value}</span>
                  </div>
                ))}
                {extractedIntel.length > 5 && (
                  <div className="text-xs text-muted-foreground/60 font-mono">
                    +{extractedIntel.length - 5} more...
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Download Report Button */}
          <Button
            onClick={handleDownloadReport}
            className="w-full font-mono gap-2 bg-primary hover:bg-primary/90 text-primary-foreground"
          >
            <Download className="h-4 w-4" />
            Download Forensic Report
          </Button>

          <Button onClick={onClose} variant="outline" className="w-full font-mono">
            Continue Monitoring
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
