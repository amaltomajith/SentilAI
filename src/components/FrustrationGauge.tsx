import { useEffect, useState } from 'react';
import { AlertTriangle, Activity, TrendingUp, Zap } from 'lucide-react';
import type { FrustrationResult } from '@/lib/frustrationAnalyzer';
import { cn } from '@/lib/utils';

interface FrustrationGaugeProps {
  result: FrustrationResult | null;
}

export function FrustrationGauge({ result }: FrustrationGaugeProps) {
  const [displayScore, setDisplayScore] = useState(0);
  const [isFlashing, setIsFlashing] = useState(false);

  useEffect(() => {
    if (result) {
      // Animate score
      const duration = 800;
      const steps = 30;
      const increment = result.score / steps;
      let current = 0;
      
      const interval = setInterval(() => {
        current += increment;
        if (current >= result.score) {
          setDisplayScore(result.score);
          clearInterval(interval);
        } else {
          setDisplayScore(Math.round(current));
        }
      }, duration / steps);

      // Flash effect for critical
      if (result.level === 'Critical') {
        setIsFlashing(true);
        const flashInterval = setInterval(() => {
          setIsFlashing(prev => !prev);
        }, 300);
        
        return () => {
          clearInterval(interval);
          clearInterval(flashInterval);
        };
      }

      return () => clearInterval(interval);
    } else {
      setDisplayScore(0);
      setIsFlashing(false);
    }
  }, [result]);

  const getGaugeColor = () => {
    if (!result) return 'stroke-muted';
    switch (result.level) {
      case 'Critical': return 'stroke-destructive';
      case 'High': return 'stroke-warning';
      case 'Medium': return 'stroke-secondary';
      case 'Low': return 'stroke-primary';
      default: return 'stroke-muted';
    }
  };

  const getLevelIcon = () => {
    if (!result) return <Activity className="h-5 w-5" />;
    switch (result.level) {
      case 'Critical': return <AlertTriangle className="h-5 w-5 text-destructive animate-pulse" />;
      case 'High': return <TrendingUp className="h-5 w-5 text-warning" />;
      case 'Medium': return <Activity className="h-5 w-5 text-secondary" />;
      case 'Low': return <Zap className="h-5 w-5 text-primary" />;
      default: return <Activity className="h-5 w-5" />;
    }
  };

  // SVG arc calculation
  const radius = 70;
  const circumference = Math.PI * radius; // Half circle
  const offset = circumference - (displayScore / 100) * circumference;

  return (
    <div className={cn(
      "h-full flex flex-col transition-all duration-300",
      isFlashing && "bg-destructive/10"
    )}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            "h-2 w-2 rounded-full",
            result?.level === 'Critical' ? "bg-destructive animate-pulse" : "bg-warning"
          )} />
          <h3 className="text-sm font-semibold text-muted-foreground font-mono uppercase tracking-wider">
            Frustration Analysis
          </h3>
        </div>
        {getLevelIcon()}
      </div>

      {/* Gauge */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="relative">
          <svg width="180" height="100" viewBox="0 0 180 100" className="transform -rotate-0">
            {/* Background arc */}
            <path
              d="M 10 90 A 70 70 0 0 1 170 90"
              fill="none"
              stroke="hsl(var(--muted))"
              strokeWidth="12"
              strokeLinecap="round"
              className="opacity-30"
            />
            {/* Foreground arc */}
            <path
              d="M 10 90 A 70 70 0 0 1 170 90"
              fill="none"
              className={cn("transition-all duration-500", getGaugeColor())}
              strokeWidth="12"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
            />
          </svg>
          
          {/* Center display */}
          <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
            <span className={cn(
              "text-4xl font-bold font-mono transition-colors duration-300",
              result?.level === 'Critical' ? "text-destructive" :
              result?.level === 'High' ? "text-warning" :
              result?.level === 'Medium' ? "text-secondary" : "text-primary"
            )}>
              {displayScore}%
            </span>
          </div>
        </div>

        {/* Level indicator */}
        <div className={cn(
          "mt-2 px-4 py-1.5 rounded-full font-mono text-sm font-bold uppercase tracking-wider transition-all duration-300",
          result?.level === 'Critical' && "bg-destructive/20 text-destructive animate-pulse",
          result?.level === 'High' && "bg-warning/20 text-warning",
          result?.level === 'Medium' && "bg-secondary/20 text-secondary",
          result?.level === 'Low' && "bg-primary/20 text-primary",
          !result && "bg-muted/20 text-muted-foreground"
        )}>
          {result?.level === 'Critical' ? '⚠️ CRITICAL AGITATION' :
           result?.level || 'AWAITING DATA'}
        </div>
      </div>

      {/* Factors list */}
      {result && result.factors.length > 0 && (
        <div className="mt-3 space-y-1.5 max-h-32 overflow-y-auto">
          {result.factors.map((factor, index) => (
            <div 
              key={index}
              className="flex items-center justify-between text-xs font-mono bg-muted/30 rounded px-2 py-1"
            >
              <span className="text-muted-foreground truncate flex-1">{factor.type}</span>
              <span className={cn(
                "ml-2 font-bold",
                factor.impact > 0 ? "text-destructive" : "text-primary"
              )}>
                {factor.impact > 0 ? '+' : ''}{factor.impact}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
