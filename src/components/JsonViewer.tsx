import { useState } from 'react';
import { Code, ChevronDown, ChevronUp, Copy, Check, Terminal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import type { AnalysisResult } from '@/lib/scamAnalyzer';

interface JsonViewerProps {
  result: AnalysisResult;
  originalMessage: string;
}

export function JsonViewer({ result, originalMessage }: JsonViewerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const jsonResponse = {
    status: 'success',
    api_version: '2.0.0',
    request_id: `req_${Date.now().toString(36)}`,
    data: {
      analysis: {
        is_scam: result.isScam,
        confidence_score: result.confidence,
        scam_type: result.scamType,
        detected_keywords: result.detectedKeywords,
        processing_time_ms: result.processingTime,
      },
      honeypot_response: {
        persona: {
          id: result.persona.id,
          name: result.persona.name,
          description: result.persona.description,
        },
        generated_reply: result.aiResponse,
      },
      extracted_intel: result.extractedIntel,
      metadata: {
        timestamp: result.timestamp,
        input_length: originalMessage.length,
        model: 'scam-defender-v2',
      },
    },
  };
  
  const jsonString = JSON.stringify(jsonResponse, null, 2);
  
  const copyJson = () => {
    navigator.clipboard.writeText(jsonString);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          variant="outline"
          className="w-full justify-between border-border/50 bg-muted/30 hover:bg-muted/50 hover:border-primary/30 font-mono"
        >
          <span className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-secondary" />
            <span className="text-muted-foreground">Developer Mode</span>
            <span className="text-xs text-muted-foreground/50">— API Response JSON</span>
          </span>
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </Button>
      </CollapsibleTrigger>
      
      <CollapsibleContent>
        <div className="mt-3 rounded-lg border border-border/50 bg-background overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 bg-muted/30 border-b border-border/50">
            <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
              <Code className="h-3 w-3" />
              <span>application/json</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={copyJson}
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
            >
              {copied ? (
                <span className="flex items-center gap-1">
                  <Check className="h-3 w-3 text-success" />
                  Copied!
                </span>
              ) : (
                <span className="flex items-center gap-1">
                  <Copy className="h-3 w-3" />
                  Copy JSON
                </span>
              )}
            </Button>
          </div>
          
          <div className="p-4 max-h-[400px] overflow-y-auto">
            <pre className="text-xs font-mono text-foreground/80 leading-relaxed">
              <code>
                {jsonString.split('\n').map((line, index) => (
                  <div key={index} className="hover:bg-muted/20">
                    <span className="inline-block w-8 text-right pr-4 text-muted-foreground/40 select-none">
                      {index + 1}
                    </span>
                    <span dangerouslySetInnerHTML={{ __html: syntaxHighlight(line) }} />
                  </div>
                ))}
              </code>
            </pre>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function syntaxHighlight(str: string): string {
  return str
    .replace(/"([^"]+)":/g, '<span class="text-secondary">"$1"</span>:')
    .replace(/: "([^"]+)"/g, ': <span class="text-success">"$1"</span>')
    .replace(/: (\d+)/g, ': <span class="text-warning">$1</span>')
    .replace(/: (true|false)/g, ': <span class="text-primary">$1</span>')
    .replace(/: (null)/g, ': <span class="text-muted-foreground">$1</span>');
}
