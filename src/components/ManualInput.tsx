import { useState } from 'react';
import { Send, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface ManualInputProps {
  onSubmit: (message: string) => Promise<void>;
  isProcessing: boolean;
}

export function ManualInput({ onSubmit, isProcessing }: ManualInputProps) {
  const [message, setMessage] = useState('');

  const handleSubmit = () => {
    if (message.trim() && !isProcessing) {
      // Avoid unhandled promise rejections (can blank-screen the app)
      void onSubmit(message.trim()).catch((err) => {
        console.error('Manual submit error:', err);
      });
      setMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
        <User className="h-4 w-4" />
        <span>MANUAL INJECTION MODE</span>
        <span className="text-primary">// Type as Scammer</span>
      </div>
      
      <div className="relative">
        <Textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Enter scammer message to test agent response..."
          disabled={isProcessing}
          className={cn(
            "min-h-[100px] font-mono bg-muted/50 border-border resize-none",
            "focus:border-primary focus:ring-primary/20",
            "placeholder:text-muted-foreground/50"
          )}
        />
        
        <Button
          onClick={handleSubmit}
          disabled={!message.trim() || isProcessing}
          className={cn(
            "absolute bottom-3 right-3",
            "bg-primary hover:bg-primary/90 text-primary-foreground",
            isProcessing && "animate-pulse"
          )}
        >
          {isProcessing ? (
            <>Processing...</>
          ) : (
            <>
              <Send className="h-4 w-4 mr-2" />
              Process
            </>
          )}
        </Button>
      </div>

      <div className="text-xs text-muted-foreground/70 font-mono">
        Tip: Try messages like "Your account will be blocked! Send ₹500 immediately!"
      </div>
    </div>
  );
}
