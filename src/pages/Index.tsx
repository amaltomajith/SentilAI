import { useState, useCallback, useRef, useEffect } from 'react';
import { Header } from '@/components/Header';
import { ModeSwitch, type OperationMode } from '@/components/ModeSwitch';
import { ManualInput } from '@/components/ManualInput';
import { ConversationLoop, type Message, type MessageStatus } from '@/components/ConversationLoop';
import { FrustrationGauge } from '@/components/FrustrationGauge';
import { TacticalAnalysisTerminal, analyzeScammerIntent, type TacticalLog } from '@/components/TacticalAnalysisTerminal';
import { IntelTable } from '@/components/IntelTable';
import { JsonViewer } from '@/components/JsonViewer';
import { SummaryPopup } from '@/components/SummaryPopup';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Play, Square, Zap } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { 
  calculateFrustration, 
  type FrustrationResult 
} from '@/lib/frustrationAnalyzer';
import { generateScammerMessage, generateRameshResponse, detectScam, generateConclusion } from '@/lib/groqApi';
import { getRandomScenarioExcluding, type Scenario } from '@/lib/scenarioDatabase';
import type { ExtractedIntel, AnalysisResult } from '@/lib/scamAnalyzer';

// Intel extraction patterns
const PATTERNS = {
  upi: /[a-zA-Z0-9._-]+@[a-zA-Z]{2,}/g,
  phone: /(?:\+91[\s-]?)?[6-9]\d{9}/g,
  url: /https?:\/\/[^\s<>"{}|\\^`\[\]]+/gi,
  bankAccount: /\b\d{9,18}\b/g,
  ifsc: /[A-Z]{4}0[A-Z0-9]{6}/g,
};

function extractIntelFromText(text: string): ExtractedIntel[] {
  const intel: ExtractedIntel[] = [];
  
  Object.values(PATTERNS).forEach(p => p.lastIndex = 0);
  
  const upiMatches = text.match(PATTERNS.upi) || [];
  upiMatches.forEach(match => {
    if (!match.includes('.com') && !match.includes('.in') && !match.includes('.org')) {
      if (!intel.some(i => i.value === match)) {
        intel.push({ type: 'UPI ID', value: match, risk: 'High' });
      }
    }
  });
  
  const phoneMatches = text.match(PATTERNS.phone) || [];
  phoneMatches.forEach(match => {
    const cleaned = match.replace(/\s/g, '');
    if (!intel.some(i => i.value === cleaned)) {
      intel.push({ type: 'Phone Number', value: cleaned, risk: 'Medium' });
    }
  });
  
  const urlMatches = text.match(PATTERNS.url) || [];
  urlMatches.forEach(match => {
    if (!intel.some(i => i.value === match)) {
      intel.push({ type: 'Phishing URL', value: match, risk: 'Critical' });
    }
  });
  
  const ifscMatches = text.match(PATTERNS.ifsc) || [];
  ifscMatches.forEach(match => {
    if (!intel.some(i => i.value === match)) {
      intel.push({ type: 'IFSC Code', value: match, risk: 'High' });
    }
  });
  
  return intel;
}

const MAX_WARFARE_EXCHANGES = 4;

const Index = () => {
  const [mode, setMode] = useState<OperationMode>('autonomous');
  
  const [isRunning, setIsRunning] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  
  const [frustration, setFrustration] = useState<FrustrationResult | null>(null);
  const [extractedIntel, setExtractedIntel] = useState<ExtractedIntel[]>([]);
  const [tacticalLogs, setTacticalLogs] = useState<TacticalLog[]>([]);
  
  const [conversationHistory, setConversationHistory] = useState<string[]>([]);
  const [exchangeCount, setExchangeCount] = useState(0);
  const [isConversationEnded, setIsConversationEnded] = useState(false);
  
  const [currentScenario, setCurrentScenario] = useState<Scenario | null>(null);
  const [stickyScenario, setStickyScenario] = useState<Scenario | null>(null);

  const [sessionDuration, setSessionDuration] = useState(0);
  const sessionTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [thinkingMessage, setThinkingMessage] = useState<string>('');

  // Summary popup state
  const [showSummary, setShowSummary] = useState(false);
  const summaryShownRef = useRef(false);

  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isRunningRef = useRef(false);

  useEffect(() => {
    isRunningRef.current = isRunning;
     
    if (isRunning) {
      sessionTimerRef.current = setInterval(() => {
        setSessionDuration(prev => prev + 1);
      }, 1000);
    } else {
      if (sessionTimerRef.current) {
        clearInterval(sessionTimerRef.current);
      }
    }
     
    return () => {
      if (sessionTimerRef.current) {
        clearInterval(sessionTimerRef.current);
      }
    };
  }, [isRunning]);

  const analysisResult: AnalysisResult | null = messages.length > 0 ? {
    isScam: true,
    confidence: frustration ? Math.min(50 + frustration.score, 99) : 75,
    scamType: 'AI-Generated Scam',
    detectedKeywords: messages
      .filter(m => m.sender === 'scammer')
      .flatMap(m => m.text.toLowerCase().split(/\s+/))
      .filter(w => ['urgent', 'immediately', 'block', 'police', 'jail', 'send', 'pay', 'otp', 'bank', 'account'].includes(w))
      .slice(0, 10),
    persona: {
      id: 'sentinel-agent',
      name: 'Sentinel',
      description: 'Autonomous Threat Neutralization Agent',
      avatar: '🛡️',
      responses: []
    },
    aiResponse: messages.filter(m => m.sender === 'agent').pop()?.text || '',
    extractedIntel,
    timestamp: new Date().toISOString(),
    processingTime: messages.length * 2000
  } : null;

  // Update message status after detection
  const updateMessageStatus = useCallback((messageId: string, status: MessageStatus, confidence: number) => {
    setMessages(prev => prev.map(m => 
      m.id === messageId ? { ...m, status, confidence } : m
    ));
  }, []);

  // Run scam detection on a message and update its status
  const runDetection = useCallback(async (messageId: string, text: string) => {
    try {
      const result = await detectScam(text);
      const status: MessageStatus = result.verdict === 'SCAM' ? 'scam' 
        : result.verdict === 'SAFE' ? 'safe' 
        : 'unknown';
      updateMessageStatus(messageId, status, result.confidence);
    } catch {
      updateMessageStatus(messageId, 'unknown', 50);
    }
  }, [updateMessageStatus]);

  // Process a scammer message with AI response (manual mode)
  const processScammerMessage = useCallback(async (scammerText: string) => {
    const msgId = `scammer-${Date.now()}`;
    const scammerMsg: Message = {
      id: msgId,
      sender: 'scammer',
      text: scammerText,
      timestamp: new Date(),
      status: 'pending',
    };
    
    setMessages(prev => [...prev, scammerMsg]);
    
    // Run detection in background
    runDetection(msgId, scammerText);
    
    // Extract intel
    const newIntel = extractIntelFromText(scammerText);
    if (newIntel.length > 0) {
      setExtractedIntel(prev => {
        const combined = [...prev];
        newIntel.forEach(ni => {
          if (!combined.some(ci => ci.value === ni.value)) {
            combined.push(ni);
          }
        });
        return combined;
      });
    }
    
    const frustrationResult = calculateFrustration(scammerText);
    setFrustration(frustrationResult);
    
    const newLogs = analyzeScammerIntent(scammerText);
    setTacticalLogs(prev => [...prev, ...newLogs]);
    
    setIsThinking(true);
    
    try {
      const newExchangeCount = exchangeCount + 1;
      setExchangeCount(newExchangeCount);
      
      const response = await generateRameshResponse(scammerText, conversationHistory, newExchangeCount);
      setConversationHistory(prev => [...prev, scammerText, response.content]);
      
      const agentMsg: Message = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: response.content,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, agentMsg]);

      // Check for summary trigger in manual mode
      if (newExchangeCount >= MAX_WARFARE_EXCHANGES && !summaryShownRef.current) {
        summaryShownRef.current = true;
        setShowSummary(true);
      }

      return response.content;
    } catch (error) {
      console.error('AI response error:', error);
      toast({
        title: "AI Error",
        description: error instanceof Error ? error.message : "Failed to generate response",
        variant: "destructive",
      });
      return null;
    } finally {
      setIsThinking(false);
    }
  }, [conversationHistory, exchangeCount, runDetection]);

  const handleManualSubmit = useCallback(async (message: string) => {
    await processScammerMessage(message);
  }, [processScammerMessage]);

  // Autonomous mode loop - all AI calls go through backend
  const runAutonomousMode = useCallback(async () => {
    setMessages([]);
    setFrustration(null);
    setExtractedIntel([]);
    setTacticalLogs([]);
    setConversationHistory([]);
    setExchangeCount(0);
    setIsConversationEnded(false);
    setIsRunning(true);
    setCurrentScenario(null);
    setStickyScenario(null);
    setThinkingMessage('');
    summaryShownRef.current = false;
    setShowSummary(false);
    
    const history: string[] = [];
    let currentExchangeCount = 0;
    
    const scenario = getRandomScenarioExcluding([]);
    setStickyScenario(scenario);
    setCurrentScenario(scenario);
    
    const runExchange = async () => {
      if (!isRunningRef.current) return;
      
      if (currentExchangeCount >= MAX_WARFARE_EXCHANGES) {
        setIsConversationEnded(true);
        setIsRunning(false);
        summaryShownRef.current = true;
        setShowSummary(true);
        toast({
          title: "Simulation Complete! 🎉",
          description: `Completed ${currentExchangeCount} exchanges in "${scenario.type}" scenario.`,
        });
        return;
      }
      
      try {
        if (!isRunningRef.current) return;
        
        let scammerText: string;
        
        if (currentExchangeCount === 0) {
          scammerText = scenario.message;
        } else {
          setThinkingMessage('Scammer thinking...');
          setIsThinking(true);
          await new Promise(resolve => setTimeout(resolve, 3000));
           
          if (!isRunningRef.current) {
            setIsThinking(false);
            setThinkingMessage('');
            return;
          }
           
          try {
            // All scammer generation now goes through backend edge function
            const scammerResponse = await generateScammerMessage(
              history, 
              currentExchangeCount,
              scenario.type,
              scenario.message
            );
            scammerText = scammerResponse.content;
          } catch (error) {
            console.error('Scammer API error:', error);
            setIsThinking(false);
            setThinkingMessage('');
            throw error;
          }
          setIsThinking(false);
          setThinkingMessage('');
        }
        
        if (!isRunningRef.current) return;
        
        const msgId = `scammer-${Date.now()}`;
        const scammerMsg: Message = {
          id: msgId,
          sender: 'scammer',
          text: scammerText,
          timestamp: new Date(),
          status: 'pending',
        };
        setMessages(prev => [...prev, scammerMsg]);

        // Run detection in background (non-blocking)
        runDetection(msgId, scammerText);
        
        const newIntel = extractIntelFromText(scammerText);
        if (newIntel.length > 0) {
          setExtractedIntel(prev => {
            const combined = [...prev];
            newIntel.forEach(ni => {
              if (!combined.some(ci => ci.value === ni.value)) {
                combined.push(ni);
              }
            });
            return combined;
          });
        }
        
        const frustrationResult = calculateFrustration(scammerText);
        setFrustration(frustrationResult);
        
        const newLogs = analyzeScammerIntent(scammerText);
        setTacticalLogs(prev => [...prev, ...newLogs]);
        
        history.push(scammerText);
        
        setThinkingMessage('Sentinel thinking...');
        setIsThinking(true);
        await new Promise(resolve => setTimeout(resolve, 3000));
         
        if (!isRunningRef.current) {
          setIsThinking(false);
          setThinkingMessage('');
          return;
        }
         
        currentExchangeCount++;
        setExchangeCount(currentExchangeCount);
        
        if (!isRunningRef.current) {
          setIsThinking(false);
          return;
        }
        
        const rameshResponse = await generateRameshResponse(scammerText, history.slice(0, -1), currentExchangeCount);
        if (!isRunningRef.current) {
          setIsThinking(false);
          return;
        }
        
        const agentMsg: Message = {
          id: `agent-${Date.now()}`,
          sender: 'agent',
          text: rameshResponse.content,
          timestamp: new Date()
        };
        setMessages(prev => [...prev, agentMsg]);
        setIsThinking(false);
        setThinkingMessage('');
        
        history.push(rameshResponse.content);
        setConversationHistory([...history]);

        // Stop and show summary at max exchanges
        if (currentExchangeCount >= MAX_WARFARE_EXCHANGES && !summaryShownRef.current) {
          summaryShownRef.current = true;
          setShowSummary(true);
          setIsConversationEnded(true);
          setIsRunning(false);
          toast({
            title: "Simulation Complete! 🎉",
            description: `Completed ${currentExchangeCount} exchanges in "${scenario.type}" scenario.`,
          });
          return;
        }
        
        if (isRunningRef.current) {
          timeoutRef.current = setTimeout(runExchange, 1000);
        }
      } catch (error) {
        console.error('Autonomous mode error:', error);
        const msg = (error instanceof Error ? error.message : String(error)).toLowerCase();
        const isRateLimited = msg.includes('429') || msg.includes('rate limit');

        toast({
          title: isRateLimited ? 'Rate limited' : 'API Error',
          description: isRateLimited
            ? 'Pausing briefly to avoid rate limits, then retrying…'
            : (error instanceof Error ? error.message : 'Failed to generate response'),
          variant: isRateLimited ? 'default' : 'destructive',
        });

        setIsThinking(false);
        setThinkingMessage('');

        if (isRateLimited && isRunningRef.current) {
          setThinkingMessage('Rate limited, cooling down...');
          timeoutRef.current = setTimeout(() => {
            setThinkingMessage('');
            runExchange();
          }, 15000);
          return;
        }

        setIsRunning(false);
      }
    };
    
    timeoutRef.current = setTimeout(runExchange, 1000);
  }, [runDetection]);

  const handleToggle = useCallback(() => {
    if (isRunning) {
      setIsRunning(false);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    } else {
      runAutonomousMode();
    }
  }, [isRunning, runAutonomousMode]);

  const handleModeChange = useCallback((newMode: OperationMode) => {
    if (isRunning) {
      setIsRunning(false);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    }
    setMode(newMode);
    setMessages([]);
    setFrustration(null);
    setExtractedIntel([]);
    setTacticalLogs([]);
    setConversationHistory([]);
    setExchangeCount(0);
    setIsConversationEnded(false);
    setThinkingMessage('');
    setSessionDuration(0);
    setCurrentScenario(null);
    setStickyScenario(null);
    summaryShownRef.current = false;
    setShowSummary(false);
  }, [isRunning]);

  return (
    <div className="min-h-screen bg-background cyber-grid matrix-bg relative overflow-hidden">
      <div className="fixed inset-0 pointer-events-none scanlines" />
      
       <Header 
         messageCount={messages.length}
         isRunning={isRunning}
         sessionDuration={sessionDuration}
         activeScenario={stickyScenario?.type || null}
       />
      
      <main className="container mx-auto px-4 py-6">
        {/* Control Panel */}
        <Card className="bg-card/80 backdrop-blur-sm border-border/50 p-6 mb-6 border-glow">
          <div className="space-y-4">
            <ModeSwitch 
              mode={mode}
              onModeChange={handleModeChange}
              disabled={isRunning}
            />
            
            <div className={cn(
              "rounded-lg border p-4 transition-all duration-500",
              isRunning 
                ? "bg-primary/10 border-primary/30 border-glow" 
                : "bg-muted/30 border-border/50"
            )}>
              {mode === 'manual' ? (
                <ManualInput onSubmit={handleManualSubmit} isProcessing={isThinking} />
              ) : (
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "h-10 w-10 rounded-full flex items-center justify-center",
                      isRunning ? "bg-primary/20 animate-pulse" : "bg-muted/50"
                    )}>
                      <Zap className={cn("h-5 w-5", isRunning ? "text-primary" : "text-muted-foreground")} />
                    </div>
                    <div>
                      <div className="font-mono font-bold text-foreground">
                        {isRunning ? 'OPERATION ACTIVE' : 'READY'}
                      </div>
                      <div className="text-xs text-muted-foreground font-mono">
                         SambaNova (Attacker) vs Groq (Defender) — All Server-Side
                      </div>
                    </div>
                  </div>
                  
                  <Button
                    onClick={handleToggle}
                    variant={isRunning ? "destructive" : "default"}
                    className={cn(
                      "font-mono font-bold gap-2",
                      !isRunning && "bg-primary hover:bg-primary/90 border-glow-strong"
                    )}
                  >
                    {isRunning ? (
                      <>
                        <Square className="h-4 w-4" />
                        ABORT
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4" />
                        ENGAGE AUTO-PILOT
                      </>
                    )}
                  </Button>
                </div>
              )}
              
              {(isRunning || isConversationEnded) && mode === 'autonomous' && (
                <div className="space-y-2 mt-4">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-muted-foreground">
                      {isConversationEnded ? 'Simulation Complete' : stickyScenario ? `Scenario: ${stickyScenario.type}` : 'Starting...'}
                    </span>
                    <span className="text-primary">{exchangeCount}/{MAX_WARFARE_EXCHANGES} exchanges</span>
                  </div>
                  <div className="h-2 bg-muted/30 rounded-full overflow-hidden">
                    <div 
                      className={cn(
                        "h-full transition-all duration-500 rounded-full",
                        isConversationEnded ? "bg-primary" : "bg-secondary animate-pulse"
                      )}
                      style={{ width: `${(exchangeCount / MAX_WARFARE_EXCHANGES) * 100}%` }}
                    />
                  </div>
                     {thinkingMessage && (
                       <div className="text-xs text-secondary font-mono animate-pulse flex items-center gap-2">
                         <div className="h-2 w-2 rounded-full bg-secondary animate-ping" />
                         {thinkingMessage}
                       </div>
                     )}
                  {stickyScenario && !isConversationEnded && (
                    <div className="text-xs text-muted-foreground font-mono flex items-center gap-2">
                      <span>Category:</span>
                      <span className={stickyScenario.category === 'scam' ? 'text-destructive' : 'text-primary'}>
                        {stickyScenario.category.toUpperCase()}
                      </span>
                      <span className="text-muted-foreground/50">•</span>
                      <span className="text-muted-foreground">
                        Locked: <span className="text-secondary">{stickyScenario.type}</span>
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5">
            <Card className="bg-card/80 backdrop-blur-sm border-border/50 p-5 h-[500px] border-glow">
              <ConversationLoop
                messages={messages}
                isThinking={isThinking}
                agentName="Sentinel"
                agentAvatar="🛡️"
              />
            </Card>
          </div>

          <div className="lg:col-span-4 space-y-6">
            <Card className="bg-card/80 backdrop-blur-sm border-border/50 p-5 h-[240px]">
              <FrustrationGauge result={frustration} />
            </Card>
            <Card className="bg-card/80 backdrop-blur-sm border-border/50 p-5 h-[240px]">
              <TacticalAnalysisTerminal logs={tacticalLogs} />
            </Card>
          </div>

          <div className="lg:col-span-3">
            <Card className="bg-card/80 backdrop-blur-sm border-border/50 p-5 h-[500px]">
              <IntelTable intel={extractedIntel} />
            </Card>
          </div>
        </div>

        {analysisResult && messages.length > 0 && (
          <div className="mt-6 slide-up">
            <JsonViewer 
              result={analysisResult} 
              originalMessage={messages.filter(m => m.sender === 'scammer').map(m => m.text).join('\n\n')}
            />
          </div>
        )}

        {!isRunning && messages.length === 0 && (
          <div className="text-center py-12 text-muted-foreground/50">
            <div className="text-6xl mb-4">🛡️</div>
            <p className="font-mono text-lg">SENTINEL READY</p>
            <p className="font-mono text-sm mt-2">
              {mode === 'manual' && "Type a scammer message above to test the AI agent"}
              {mode === 'autonomous' && "Click 'Engage Auto-Pilot' for hybrid simulation with preset scenarios"}
            </p>
          </div>
        )}
      </main>
      
      <footer className="border-t border-border/30 py-4 mt-8">
        <div className="container mx-auto px-4 text-center">
          <div className="flex items-center justify-center gap-4">
            <p className="text-xs font-mono text-muted-foreground/50">
              🛡️ Sentinel • Dual-Mode Operations • Autonomous Agent v3.0
            </p>
            <span className="text-muted-foreground/30">|</span>
            <a 
              href={`${import.meta.env.VITE_SUPABASE_URL}/functions/v1/evaluate-scam`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono text-primary/70 hover:text-primary transition-colors flex items-center gap-1"
            >
              <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              API Endpoint Status: Active
            </a>
          </div>
        </div>
      </footer>

      {/* Summary Popup */}
      <SummaryPopup
        open={showSummary}
        onClose={() => setShowSummary(false)}
        messages={messages}
        extractedIntel={extractedIntel}
        exchangeCount={exchangeCount}
        scenarioType={stickyScenario?.type}
      />
    </div>
  );
};

export default Index;
