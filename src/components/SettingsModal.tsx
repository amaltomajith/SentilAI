 import { useState, useEffect } from "react";
 import {
   Dialog,
   DialogContent,
   DialogHeader,
   DialogTitle,
   DialogTrigger,
 } from "@/components/ui/dialog";
 import { Button } from "@/components/ui/button";
 import { Input } from "@/components/ui/input";
 import { Label } from "@/components/ui/label";
 import { Settings, Eye, EyeOff, Save } from "lucide-react";
 import { toast } from "@/hooks/use-toast";
 
 const GROQ_KEY = "scamdefense_groq_api_key";
 const SAMBANOVA_KEY = "scamdefense_sambanova_api_key";
 
export function getStoredGroqKey(): string {
  return localStorage.getItem(GROQ_KEY) || "";
}

export function getStoredSambanovaKey(): string {
  return localStorage.getItem(SAMBANOVA_KEY) || "";
}
 
 export function SettingsModal() {
   const [open, setOpen] = useState(false);
   const [groqKey, setGroqKey] = useState('');
   const [sambanovaKey, setSambanovaKey] = useState('');
   const [showGroq, setShowGroq] = useState(false);
   const [showSambanova, setShowSambanova] = useState(false);
 
  useEffect(() => {
    if (open) {
      // Only load user-entered custom keys from localStorage, never backend defaults
      setGroqKey(localStorage.getItem(GROQ_KEY) || '');
      setSambanovaKey(localStorage.getItem(SAMBANOVA_KEY) || '');
      setShowGroq(false);
      setShowSambanova(false);
    }
  }, [open]);
 
   const handleSave = () => {
     localStorage.setItem(GROQ_KEY, groqKey.trim());
     localStorage.setItem(SAMBANOVA_KEY, sambanovaKey.trim());
     toast({
       title: "Settings Saved",
       description: "API keys stored in localStorage.",
     });
     setOpen(false);
   };
 
   return (
     <Dialog open={open} onOpenChange={setOpen}>
       <DialogTrigger asChild>
         <Button variant="ghost" size="icon" className="text-muted-foreground hover:text-primary">
           <Settings className="h-5 w-5" />
         </Button>
       </DialogTrigger>
       <DialogContent className="bg-card border-border">
         <DialogHeader>
           <DialogTitle className="font-mono text-primary">API Configuration</DialogTitle>
         </DialogHeader>
        <div className="space-y-4 py-4">
             {/* Info Banner */}
             <div className="bg-primary/10 border border-primary/20 rounded-md p-3">
               <p className="text-xs text-primary font-mono">
                 ✓ All API keys are configured server-side. Autopilot works out of the box!
               </p>
               <p className="text-xs text-muted-foreground mt-1">
                 This page is only for advanced users who want to override with their own keys.
                 Keys entered here are stored in your browser's localStorage and are used only for manual mode overrides.
               </p>
             </div>

            {/* Groq API Key */}
            <div className="space-y-2">
              <Label htmlFor="groq-key" className="font-mono text-xs text-muted-foreground">
                Groq API Key (Defender - Ramesh) - Optional Override
              </Label>
              <div className="relative">
                <Input
                  id="groq-key"
                  type={showGroq ? 'text' : 'password'}
                  value={groqKey}
                  onChange={(e) => setGroqKey(e.target.value)}
                  placeholder="gsk_... (leave empty to use default)"
                  className="pr-10 font-mono text-sm"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowGroq(!showGroq)}
                >
                  {showGroq ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Get your key from{" "}
                <a href="https://console.groq.com/keys" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                  console.groq.com/keys
                </a>
              </p>
            </div>

            {/* SambaNova API Key */}
            <div className="space-y-2">
              <Label htmlFor="sambanova-key" className="font-mono text-xs text-muted-foreground">
                SambaNova API Key (Attacker - Scammer) - Optional Override
              </Label>
              <div className="relative">
                <Input
                  id="sambanova-key"
                  type={showSambanova ? "text" : "password"}
                  value={sambanovaKey}
                  onChange={(e) => setSambanovaKey(e.target.value)}
                  placeholder="(leave empty to use default)"
                  className="pr-10 font-mono text-sm"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowSambanova(!showSambanova)}
                >
                  {showSambanova ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Get your key from{" "}
                <a href="https://cloud.sambanova.ai/apis" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                  cloud.sambanova.ai/apis
                </a>
              </p>
            </div>

            <Button onClick={handleSave} className="w-full font-mono gap-2">
              <Save className="h-4 w-4" />
              Save Custom API Keys
            </Button>

            <p className="text-xs text-muted-foreground text-center">
              Custom keys are stored locally in your browser and override defaults.
            </p>
          </div>
       </DialogContent>
     </Dialog>
   );
 }