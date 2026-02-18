import { Hand, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

export type OperationMode = 'manual' | 'autonomous';

interface ModeSwitchProps {
  mode: OperationMode;
  onModeChange: (mode: OperationMode) => void;
  disabled?: boolean;
}

const modes: { id: OperationMode; label: string; icon: typeof Hand; description: string }[] = [
  { 
    id: 'autonomous', 
    label: 'WARFARE', 
    icon: Zap, 
    description: 'Real-Time AI' 
  },
  { 
    id: 'manual', 
    label: 'MANUAL', 
    icon: Hand, 
    description: 'Human-in-the-Loop' 
  },
];

export function ModeSwitch({ mode, onModeChange, disabled }: ModeSwitchProps) {
  return (
    <div className="flex items-center gap-4">
      {/* Segmented Toggle */}
      <div className="flex-1">
        <div className="text-xs font-mono text-muted-foreground mb-2 uppercase tracking-wider">
          Operation Mode
        </div>
        <div className="inline-flex rounded-lg border border-border bg-muted/30 p-1">
          {modes.map(({ id, label, icon: Icon, description }) => (
            <button
              key={id}
              onClick={() => onModeChange(id)}
              disabled={disabled}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-md font-mono text-sm transition-all duration-300",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                mode === id
                  ? "bg-primary text-primary-foreground shadow-lg border-glow"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              )}
            >
              <Icon className="h-4 w-4" />
              <div className="text-left">
                <div className="font-bold">{label}</div>
                <div className="text-[10px] opacity-70">{description}</div>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
