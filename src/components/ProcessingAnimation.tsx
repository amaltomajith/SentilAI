import { Shield, Scan, Brain, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

const STEPS = [
  { icon: Scan, text: 'Scanning message patterns...' },
  { icon: Brain, text: 'AI analyzing threat level...' },
  { icon: Shield, text: 'Deploying honey-pot agent...' },
  { icon: Zap, text: 'Generating counter-response...' },
];

export function ProcessingAnimation() {
  const [currentStep, setCurrentStep] = useState(0);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentStep((prev) => (prev + 1) % STEPS.length);
    }, 600);
    return () => clearInterval(interval);
  }, []);
  
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="relative mb-8">
        <div className="h-24 w-24 rounded-full border-2 border-primary/30 flex items-center justify-center pulse-glow">
          <Shield className="h-12 w-12 text-primary animate-pulse" />
        </div>
        <div className="absolute inset-0 rounded-full border-2 border-primary/20 animate-ping" />
      </div>
      
      <div className="space-y-3 text-center">
        {STEPS.map((step, index) => {
          const Icon = step.icon;
          const isActive = index === currentStep;
          const isPast = index < currentStep;
          
          return (
            <div
              key={index}
              className={`flex items-center gap-3 transition-all duration-300 ${
                isActive ? 'text-primary text-glow' : isPast ? 'text-muted-foreground' : 'text-muted-foreground/30'
              }`}
            >
              <Icon className={`h-4 w-4 ${isActive ? 'animate-pulse' : ''}`} />
              <span className="font-mono text-sm">{step.text}</span>
              {isPast && <span className="text-success text-xs">✓</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
