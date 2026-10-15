import { Link } from 'react-router-dom';
import { Sprite } from '@/components/pixel/Sprite';

export function Logo({ to = '/', size = 26 }: { to?: string; size?: number }) {
  return (
    <Link to={to} className="group inline-flex items-center gap-2.5" aria-label="Sentinel home">
      <Sprite name="shield" size={size} className="transition-transform duration-300 group-hover:-rotate-6" />
      <span className="text-[17px] font-semibold tracking-tight text-foreground">Sentinel</span>
    </Link>
  );
}