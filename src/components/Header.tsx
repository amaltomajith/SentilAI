 import { Shield, MessageSquare, Brain, Clock } from 'lucide-react';
 import { SettingsModal } from './SettingsModal';
 import { Badge } from '@/components/ui/badge';
 
 interface HeaderProps {
   messageCount?: number;
   isRunning?: boolean;
   sessionDuration?: number;
   activeScenario?: string | null;
 }

 export function Header({ messageCount = 0, isRunning = false, sessionDuration = 0, activeScenario = null }: HeaderProps) {
   const formatDuration = (seconds: number) => {
     const mins = Math.floor(seconds / 60);
     const secs = seconds % 60;
     return `${mins}:${secs.toString().padStart(2, '0')}`;
   };
 
  return (
    <header className="border-b border-border/50 bg-card/50 backdrop-blur-sm">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Shield className="h-10 w-10 text-primary" />
               {isRunning && (
                 <div className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-primary animate-pulse" />
               )}
            </div>
            <div>
              <h1 className="text-2xl font-bold text-primary text-glow font-mono tracking-tight">
                SENTINEL
              </h1>
              <p className="text-xs text-muted-foreground font-mono">
                Autonomous Agent • Cyber Command Center
              </p>
            </div>
          </div>
          
          <div className="hidden md:flex items-center gap-6">
             {isRunning && activeScenario && (
               <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/30">
                 <Badge variant="outline" className="text-xs font-mono border-destructive/50 text-destructive">
                   SambaNova (Attacker)
                 </Badge>
                 <span className="text-xs text-muted-foreground">vs</span>
                 <Badge variant="outline" className="text-xs font-mono border-primary/50 text-primary">
                   Groq (Defender)
                 </Badge>
               </div>
             )}
             <StatDisplay 
               icon={MessageSquare} 
               label="Messages" 
               value={messageCount.toString()} 
             />
             <StatDisplay 
               icon={Brain} 
               label="AI Status" 
               value={isRunning ? "ACTIVE" : "IDLE"} 
               highlight={isRunning}
             />
             <StatDisplay 
               icon={Clock} 
               label="Session" 
               value={formatDuration(sessionDuration)} 
             />
             <SettingsModal />
          </div>
        </div>
      </div>
    </header>
  );
}

 function StatDisplay({ 
   icon: Icon, 
   label, 
   value,
   highlight = false
 }: { 
   icon: React.ElementType; 
   label: string; 
   value: string;
   highlight?: boolean;
}) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <span className="text-muted-foreground">{label}</span>
       <span className={highlight ? "text-primary font-bold" : "text-foreground"}>{value}</span>
       {highlight && <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />}
    </div>
  );
}
