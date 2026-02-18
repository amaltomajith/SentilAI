import { useEffect, useRef } from 'react';
import { Bot, User, Loader2, ShieldAlert, ShieldCheck, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';

export type MessageStatus = 'pending' | 'scam' | 'safe' | 'unknown';

export interface Message {
  id: string;
  sender: 'scammer' | 'agent';
  text: string;
  timestamp: Date;
  status?: MessageStatus;
  confidence?: number;
}

interface ConversationLoopProps {
  messages: Message[];
  isThinking: boolean;
  agentName: string;
  agentAvatar: string;
}

function getSenderConfig(message: Message) {
  if (message.sender === 'agent') {
    return null; // agent always uses primary colors
  }

  const status = message.status || 'pending';

  switch (status) {
    case 'scam':
      return {
        label: 'SCAMMER',
        bgClass: 'bg-destructive/10 border-destructive/20',
        avatarBg: 'bg-destructive/20',
        iconColor: 'text-destructive',
        labelColor: 'text-destructive',
        icon: ShieldAlert,
      };
    case 'safe':
      return {
        label: 'FALSE POSITIVE',
        bgClass: 'bg-emerald-500/10 border-emerald-500/20',
        avatarBg: 'bg-emerald-500/20',
        iconColor: 'text-emerald-500',
        labelColor: 'text-emerald-500',
        icon: ShieldCheck,
      };
    case 'unknown':
      return {
        label: 'ANALYZING...',
        bgClass: 'bg-blue-500/10 border-blue-500/20',
        avatarBg: 'bg-blue-500/20',
        iconColor: 'text-blue-500',
        labelColor: 'text-blue-500',
        icon: HelpCircle,
      };
    case 'pending':
    default:
      return {
        label: 'ANONYMOUS',
        bgClass: 'bg-blue-500/10 border-blue-500/20',
        avatarBg: 'bg-blue-500/20',
        iconColor: 'text-blue-500',
        labelColor: 'text-blue-500',
        icon: User,
      };
  }
}

export function ConversationLoop({ 
  messages, 
  isThinking, 
  agentName,
  agentAvatar 
}: ConversationLoopProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isThinking]);

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={cn(
            "h-2 w-2 rounded-full",
            messages.length > 0 ? "bg-primary animate-pulse" : "bg-muted-foreground/50"
          )} />
          <h3 className="text-sm font-semibold text-muted-foreground font-mono uppercase tracking-wider">
            Live Conversation Feed
          </h3>
        </div>
        <span className="text-xs font-mono text-muted-foreground">
          {messages.length} messages
        </span>
      </div>

      {messages.length > 0 && (
        <div className="flex items-center gap-2 mb-3 px-3 py-2 bg-primary/10 rounded-lg border border-primary/20">
          <span className="text-2xl">{agentAvatar}</span>
          <div>
            <div className="font-mono font-bold text-primary text-sm">{agentName}</div>
            <div className="text-xs text-muted-foreground font-mono">Active Agent</div>
          </div>
        </div>
      )}

      <ScrollArea className="flex-1 pr-4" ref={scrollRef}>
        <div className="space-y-3">
          {messages.length === 0 && !isThinking && (
            <div className="flex items-center justify-center h-48 text-muted-foreground/50">
              <div className="text-center">
                <Bot className="h-10 w-10 mx-auto mb-2 opacity-50" />
                <p className="font-mono text-sm">Conversation will appear here</p>
                <p className="font-mono text-xs">Start simulation to begin</p>
              </div>
            </div>
          )}

          {messages.map((message, index) => {
            const senderConfig = getSenderConfig(message);
            const isAgent = message.sender === 'agent';
            const IconComponent = senderConfig?.icon || User;

            return (
              <div 
                key={message.id} 
                className={cn(
                  "flex gap-2 animate-fade-in",
                  isAgent && "flex-row-reverse"
                )}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className={cn(
                  "flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center text-lg",
                  isAgent ? "bg-primary/20" : senderConfig?.avatarBg
                )}>
                  {isAgent ? (
                    <span>{agentAvatar}</span>
                  ) : (
                    <IconComponent className={cn("h-4 w-4", senderConfig?.iconColor)} />
                  )}
                </div>
                
                <div className={cn(
                  "flex-1 rounded-lg p-3 max-w-[85%] border",
                  isAgent
                    ? "bg-primary/10 border-primary/20 rounded-tr-none border-glow"
                    : cn(senderConfig?.bgClass, "rounded-tl-none")
                )}>
                  <div className={cn(
                    "text-xs font-mono mb-1 flex items-center gap-1.5",
                    isAgent ? "text-primary" : senderConfig?.labelColor
                  )}>
                    {isAgent ? agentName.toUpperCase() : senderConfig?.label}
                    {!isAgent && message.confidence !== undefined && message.status !== 'pending' && (
                      <span className="text-[10px] opacity-60">({message.confidence}%)</span>
                    )}
                  </div>
                  <p className="text-sm text-foreground leading-relaxed">
                    {message.text}
                  </p>
                  <div className="text-xs text-muted-foreground/50 font-mono mt-1">
                    {message.timestamp.toLocaleTimeString()}
                  </div>
                </div>
              </div>
            );
          })}

          {isThinking && (
            <div className="flex gap-2 animate-fade-in">
              <div className="flex-shrink-0 h-8 w-8 rounded-full bg-primary/20 flex items-center justify-center">
                <span className="text-lg">{agentAvatar}</span>
              </div>
              <div className="bg-primary/10 border border-primary/20 rounded-lg rounded-tl-none p-3">
                <div className="flex items-center gap-2 text-primary">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span className="font-mono text-sm">Thinking...</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
