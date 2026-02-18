import { Play, Square, Zap, Bot, Shield } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import type { ScamScenario } from '@/lib/scamScenarios';

interface SimulationControlProps {
  isRunning: boolean;
  onToggle: () => void;
  currentScenario: ScamScenario | null;
  messageCount: number;
  totalMessages: number;
}

export function SimulationControl({ 
  isRunning, 
  onToggle, 
  currentScenario, 
  messageCount,
  totalMessages 
}: SimulationControlProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-semibold text-foreground font-mono">
            AUTONOMOUS AGENT CONTROL
          </h2>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-muted-foreground uppercase">
            {isRunning ? 'Active' : 'Standby'}
          </span>
          <Switch 
            checked={isRunning} 
            onCheckedChange={onToggle}
            className="data-[state=checked]:bg-primary"
          />
        </div>
      </div>

      {/* Status Panel */}
      <div className={cn(
        "rounded-lg border p-4 transition-all duration-500",
        isRunning 
          ? "bg-primary/10 border-primary/30 border-glow" 
          : "bg-muted/30 border-border/50"
      )}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={cn(
              "h-10 w-10 rounded-full flex items-center justify-center",
              isRunning ? "bg-primary/20 animate-pulse" : "bg-muted/50"
            )}>
              {isRunning ? (
                <Bot className="h-5 w-5 text-primary" />
              ) : (
                <Zap className="h-5 w-5 text-muted-foreground" />
              )}
            </div>
            <div>
              <div className="font-mono font-bold text-foreground">
                {isRunning ? 'AGENT DEPLOYED' : 'SYSTEM READY'}
              </div>
              <div className="text-xs text-muted-foreground font-mono">
                {currentScenario ? currentScenario.name : 'Awaiting scenario selection'}
              </div>
            </div>
          </div>

          <Button
            onClick={onToggle}
            variant={isRunning ? "destructive" : "default"}
            className={cn(
              "font-mono font-bold gap-2",
              !isRunning && "bg-primary hover:bg-primary/90 border-glow-strong"
            )}
          >
            {isRunning ? (
              <>
                <Square className="h-4 w-4" />
                ABORT MISSION
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                START SIMULATION
              </>
            )}
          </Button>
        </div>

        {/* Progress indicator */}
        {isRunning && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-muted-foreground">Conversation Progress</span>
              <span className="text-primary">{messageCount}/{totalMessages * 2} messages</span>
            </div>
            <div className="h-2 bg-muted/50 rounded-full overflow-hidden">
              <div 
                className="h-full bg-primary transition-all duration-500 rounded-full"
                style={{ width: `${(messageCount / (totalMessages * 2)) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* Scenario info */}
        {currentScenario && isRunning && (
          <div className="mt-3 pt-3 border-t border-border/30">
            <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
              <span className="px-2 py-0.5 bg-warning/20 text-warning rounded">
                {currentScenario.category}
              </span>
              <span>•</span>
              <span>Scenario: {currentScenario.name}</span>
            </div>
          </div>
        )}
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-muted/30 rounded-lg p-3 border border-border/30">
          <div className="text-2xl font-bold font-mono text-primary">5</div>
          <div className="text-xs text-muted-foreground font-mono">Scenarios</div>
        </div>
        <div className="bg-muted/30 rounded-lg p-3 border border-border/30">
          <div className="text-2xl font-bold font-mono text-secondary">25</div>
          <div className="text-xs text-muted-foreground font-mono">Responses</div>
        </div>
        <div className="bg-muted/30 rounded-lg p-3 border border-border/30">
          <div className="text-2xl font-bold font-mono text-warning">∞</div>
          <div className="text-xs text-muted-foreground font-mono">Confusion</div>
        </div>
      </div>
    </div>
  );
}
