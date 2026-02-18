import { useState } from 'react';
import { Crosshair, Zap, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

interface ScamInputProps {
  onAnalyze: (message: string) => void;
  isProcessing: boolean;
}

const SAMPLE_SCAMS = [
  "CONGRATULATIONS! You have WON ₹50,00,000 in the Amazon Lucky Draw! Send ₹500 registration fee to claim. UPI: lucky_draw@paytm. Contact: 9876543210. ACT NOW! Limited time offer!",
  "Dear Customer, Your SBI account has been BLOCKED due to KYC expiry. Click here to update: http://sbi-kyc-update.fake.com. Failure to update within 24 hours will result in permanent suspension.",
  "Hi, I am calling from Income Tax Department. There is a warrant against your PAN card for tax evasion. Pay ₹25,000 immediately to avoid arrest. Send to suresh.sharma@ybl",
];

export function ScamInput({ onAnalyze, isProcessing }: ScamInputProps) {
  const [message, setMessage] = useState('');
  
  const handleSubmit = () => {
    if (message.trim()) {
      onAnalyze(message);
    }
  };
  
  const loadSample = () => {
    const randomSample = SAMPLE_SCAMS[Math.floor(Math.random() * SAMPLE_SCAMS.length)];
    setMessage(randomSample);
  };
  
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-warning" />
          <h2 className="text-lg font-semibold text-foreground font-mono">
            INCOMING THREAT ANALYSIS
          </h2>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadSample}
          className="border-border/50 text-muted-foreground hover:text-foreground hover:border-primary/50 font-mono text-xs"
        >
          Load Sample Scam
        </Button>
      </div>
      
      <div className="relative">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Paste suspicious message here for analysis..."
          className="min-h-[150px] bg-input/50 border-border/50 text-foreground placeholder:text-muted-foreground/50 font-mono text-sm resize-none focus:border-primary focus:ring-primary/20 focus:border-glow"
        />
        <div className="absolute top-2 right-2 text-xs text-muted-foreground/50 font-mono">
          {message.length} chars
        </div>
      </div>
      
      <Button
        onClick={handleSubmit}
        disabled={!message.trim() || isProcessing}
        className="w-full bg-primary text-primary-foreground hover:bg-primary/90 font-mono font-bold text-base py-6 border-glow-strong transition-all duration-300 disabled:opacity-50"
      >
        {isProcessing ? (
          <span className="flex items-center gap-2">
            <Zap className="h-5 w-5 animate-pulse" />
            PROCESSING THREAT...
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <Crosshair className="h-5 w-5" />
            ACTIVATE HONEY-POT
          </span>
        )}
      </Button>
    </div>
  );
}
