import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { LinkStep, TargetStep } from '@/components/ProtectPanel';

export default function Connect() {
  return (
    <div className="space-y-8">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tightest sm:text-4xl">Connect WhatsApp, then name the scammer.</h1>
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">Sentinel links to your WhatsApp as a device. It reads and answers only the number you add. Everything else stays on your phone.</p>
      </div>
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <LinkStep />
        <div className="space-y-5">
          <TargetStep />
          <ul className="space-y-2 px-1 text-[13.5px] leading-relaxed text-muted-foreground">
            <li>The agent never starts a chat. It answers once that number messages you.</li>
            <li>It never pays, never gives real bank details, never shares your private information.</li>
            <li>Remove the number or unlink at any time and it stops immediately.</li>
          </ul>
        </div>
      </div>
      <div className="flex justify-end"><Button asChild size="lg"><Link to="/live">Go to live view</Link></Button></div>
    </div>
  );
}