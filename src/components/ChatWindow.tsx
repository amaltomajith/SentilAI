import { Bot, User, Copy, Check } from 'lucide-react';
import { useState } from 'react';
import type { AnalysisResult } from '@/lib/scamAnalyzer';
import { Button } from '@/components/ui/button';

interface ChatWindowProps {
  result: AnalysisResult;
  originalMessage: string;
}

export function ChatWindow({ result, originalMessage }: ChatWindowProps) {
  const [copied, setCopied] = useState(false);
  const { persona, aiResponse } = result;
  
  const copyResponse = () => {
    navigator.clipboard.writeText(aiResponse);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-secondary animate-pulse" />
          <h3 className="text-sm font-semibold text-muted-foreground font-mono uppercase tracking-wider">
            Honey-Pot Response
          </h3>
        </div>
      </div>
      
      {/* Persona Card */}
      <div className="bg-muted/30 rounded-lg p-3 mb-4 border border-border/50">
        <div className="flex items-center gap-3">
          <div className="text-4xl">{persona.avatar}</div>
          <div>
            <div className="font-semibold text-foreground">{persona.name}</div>
            <div className="text-xs text-muted-foreground font-mono">{persona.description}</div>
          </div>
        </div>
      </div>
      
      {/* Chat Messages */}
      <div className="flex-1 space-y-3 overflow-y-auto">
        {/* Scammer Message */}
        <div className="flex gap-2">
          <div className="flex-shrink-0 h-8 w-8 rounded-full bg-destructive/20 flex items-center justify-center">
            <User className="h-4 w-4 text-destructive" />
          </div>
          <div className="flex-1 bg-destructive/10 border border-destructive/20 rounded-lg rounded-tl-none p-3">
            <div className="text-xs text-destructive font-mono mb-1">SCAMMER</div>
            <p className="text-sm text-foreground/80 line-clamp-3">{originalMessage.slice(0, 150)}...</p>
          </div>
        </div>
        
        {/* AI Response */}
        <div className="flex gap-2">
          <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center">
            <Bot className="h-4 w-4 text-primary" />
          </div>
          <div className="flex-1 bg-primary/10 border border-primary/20 rounded-lg rounded-tl-none p-3 border-glow">
            <div className="flex items-center justify-between mb-1">
              <div className="text-xs text-primary font-mono">{persona.name.toUpperCase()}</div>
              <Button
                variant="ghost"
                size="sm"
                onClick={copyResponse}
                className="h-6 px-2 text-xs text-muted-foreground hover:text-foreground"
              >
                {copied ? (
                  <Check className="h-3 w-3 text-success" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
            <p className="text-sm text-foreground leading-relaxed">{aiResponse}</p>
          </div>
        </div>
      </div>
      
      {/* Status */}
      <div className="mt-4 pt-3 border-t border-border/30">
        <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
          <Bot className="h-3 w-3 text-primary" />
          <span>AI agent deployed as <span className="text-secondary">{persona.name}</span></span>
        </div>
      </div>
    </div>
  );
}
