import { ShieldAlert, ShieldCheck, TrendingUp, Clock, Tag } from 'lucide-react';
import type { AnalysisResult } from '@/lib/scamAnalyzer';

interface DetectionCardProps {
  result: AnalysisResult;
}

export function DetectionCard({ result }: DetectionCardProps) {
  const { isScam, confidence, scamType, detectedKeywords, processingTime } = result;
  
  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-2 mb-4">
        <div className="h-2 w-2 rounded-full bg-destructive animate-pulse" />
        <h3 className="text-sm font-semibold text-muted-foreground font-mono uppercase tracking-wider">
          Threat Assessment
        </h3>
      </div>
      
      {/* Main Badge */}
      <div className={`
        relative p-6 rounded-lg border-2 text-center mb-4
        ${isScam 
          ? 'bg-destructive/10 border-destructive border-glow-red' 
          : 'bg-success/10 border-success border-glow'
        }
      `}>
        <div className="absolute top-2 right-2">
          {isScam ? (
            <ShieldAlert className="h-8 w-8 text-destructive animate-pulse" />
          ) : (
            <ShieldCheck className="h-8 w-8 text-success" />
          )}
        </div>
        
        <div className={`
          text-3xl font-black font-mono tracking-tight mb-2
          ${isScam ? 'text-destructive text-glow-red' : 'text-success text-glow'}
        `}>
          {isScam ? 'SCAM DETECTED' : 'SAFE MESSAGE'}
        </div>
        
        <div className="text-sm text-muted-foreground font-mono">
          Classification: <span className={isScam ? 'text-destructive' : 'text-success'}>{scamType}</span>
        </div>
      </div>
      
      {/* Confidence Meter */}
      <div className="space-y-2 mb-4">
        <div className="flex items-center justify-between text-sm font-mono">
          <span className="text-muted-foreground flex items-center gap-1">
            <TrendingUp className="h-4 w-4" />
            Confidence Score
          </span>
          <span className={`font-bold ${confidence > 70 ? 'text-destructive' : confidence > 40 ? 'text-warning' : 'text-success'}`}>
            {confidence}%
          </span>
        </div>
        <div className="h-3 bg-muted rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-1000 ease-out rounded-full ${
              confidence > 70 ? 'bg-destructive' : confidence > 40 ? 'bg-warning' : 'bg-success'
            }`}
            style={{ width: `${confidence}%` }}
          />
        </div>
      </div>
      
      {/* Processing Time */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono mb-4">
        <Clock className="h-3 w-3" />
        Analysis completed in {processingTime}ms
      </div>
      
      {/* Detected Keywords */}
      {detectedKeywords.length > 0 && (
        <div className="flex-1">
          <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono mb-2">
            <Tag className="h-3 w-3" />
            Detected Indicators ({detectedKeywords.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {detectedKeywords.slice(0, 8).map((keyword, index) => (
              <span
                key={index}
                className="px-2 py-0.5 text-xs font-mono bg-destructive/20 text-destructive border border-destructive/30 rounded"
              >
                {keyword}
              </span>
            ))}
            {detectedKeywords.length > 8 && (
              <span className="px-2 py-0.5 text-xs font-mono text-muted-foreground">
                +{detectedKeywords.length - 8} more
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
