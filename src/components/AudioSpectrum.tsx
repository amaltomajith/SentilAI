import { useEffect, useState } from 'react';
import { Radio, Mic, AlertTriangle, Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AudioSpectrumProps {
  isActive: boolean;
  onAnalysisComplete?: (result: 'natural' | 'synthetic') => void;
}

export function AudioSpectrum({ isActive, onAnalysisComplete }: AudioSpectrumProps) {
  const [isAnimating, setIsAnimating] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<'natural' | 'synthetic' | null>(null);
  const [bars, setBars] = useState<number[]>(Array(24).fill(20));

  useEffect(() => {
    if (isActive) {
      setIsAnimating(true);
      setAnalysisResult(null);

      // Animate bars
      const barInterval = setInterval(() => {
        setBars(prev => prev.map(() => Math.random() * 80 + 20));
      }, 80);

      // Stop after 3 seconds and show result
      const timeout = setTimeout(() => {
        clearInterval(barInterval);
        setIsAnimating(false);
        
        // Random result - 40% chance of synthetic detection
        const result = Math.random() < 0.4 ? 'synthetic' : 'natural';
        setAnalysisResult(result);
        setBars(Array(24).fill(20));
        
        if (onAnalysisComplete) {
          onAnalysisComplete(result);
        }
      }, 3000);

      return () => {
        clearInterval(barInterval);
        clearTimeout(timeout);
      };
    }
  }, [isActive, onAnalysisComplete]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            "h-2 w-2 rounded-full",
            isAnimating ? "bg-warning animate-pulse" : "bg-primary"
          )} />
          <h3 className="text-sm font-semibold text-muted-foreground font-mono uppercase tracking-wider">
            Deepfake Voice Detection
          </h3>
        </div>
        <Radio className={cn(
          "h-4 w-4 transition-colors",
          isAnimating ? "text-warning animate-pulse" : "text-muted-foreground"
        )} />
      </div>

      {/* Waveform visualizer */}
      <div className="flex-1 flex items-center justify-center bg-muted/20 rounded-lg border border-border/30 p-4 relative overflow-hidden">
        {/* Grid background */}
        <div className="absolute inset-0 opacity-10">
          <div className="grid grid-cols-12 gap-0 h-full w-full">
            {Array(12).fill(null).map((_, i) => (
              <div key={i} className="border-r border-primary/30" />
            ))}
          </div>
          <div className="absolute inset-0 grid grid-rows-6 gap-0">
            {Array(6).fill(null).map((_, i) => (
              <div key={i} className="border-b border-primary/30" />
            ))}
          </div>
        </div>

        {/* Spectrum bars */}
        <div className="flex items-end justify-center gap-1 h-full w-full z-10">
          {bars.map((height, index) => (
            <div
              key={index}
              className={cn(
                "w-2 rounded-t transition-all",
                isAnimating ? "duration-75" : "duration-500",
                analysisResult === 'synthetic' ? "bg-destructive" :
                analysisResult === 'natural' ? "bg-primary" :
                isAnimating ? "bg-secondary" : "bg-muted-foreground/30"
              )}
              style={{
                height: `${isAnimating ? height : 20}%`,
                opacity: isAnimating ? 1 : 0.5
              }}
            />
          ))}
        </div>

        {/* Center status overlay */}
        {!isAnimating && (
          <div className="absolute inset-0 flex items-center justify-center">
            {analysisResult === null ? (
              <div className="flex items-center gap-2 text-muted-foreground/50">
                <Mic className="h-5 w-5" />
                <span className="font-mono text-sm">Awaiting Voice Input</span>
              </div>
            ) : analysisResult === 'natural' ? (
              <div className="flex items-center gap-2 px-4 py-2 bg-primary/20 rounded-lg border border-primary/30 animate-scale-in">
                <Check className="h-5 w-5 text-primary" />
                <span className="font-mono text-sm font-bold text-primary">NATURAL VOICE</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 px-4 py-2 bg-destructive/20 rounded-lg border border-destructive/30 animate-scale-in">
                <AlertTriangle className="h-5 w-5 text-destructive animate-pulse" />
                <span className="font-mono text-sm font-bold text-destructive">SYNTHETIC/AI VOICE DETECTED</span>
              </div>
            )}
          </div>
        )}

        {/* Scanning overlay when active */}
        {isAnimating && (
          <div className="absolute inset-0 pointer-events-none">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-secondary to-transparent animate-pulse" />
            <div className="absolute bottom-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-secondary to-transparent animate-pulse" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="font-mono text-xs text-secondary animate-pulse uppercase tracking-widest">
                Analyzing Voice Pattern...
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Status bar */}
      <div className="mt-3 flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-2">
          <div className={cn(
            "h-1.5 w-1.5 rounded-full",
            isAnimating ? "bg-secondary animate-pulse" : 
            analysisResult === 'synthetic' ? "bg-destructive" :
            analysisResult === 'natural' ? "bg-primary" : "bg-muted-foreground/50"
          )} />
          <span className="text-muted-foreground">
            {isAnimating ? 'Processing audio stream...' :
             analysisResult === 'synthetic' ? 'Warning: AI-generated audio' :
             analysisResult === 'natural' ? 'Voice pattern verified' : 'Ready for analysis'}
          </span>
        </div>
        <span className="text-muted-foreground/50">
          {isAnimating ? 'FFT Analysis' : 'Neural Network v2.1'}
        </span>
      </div>
    </div>
  );
}
