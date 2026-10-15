import { Sprite, type SpriteName } from '@/components/pixel/Sprite';

const ITEMS: { label: string; sprite: SpriteName }[] = [
  { label: 'Fake KYC alerts', sprite: 'shield' }, { label: 'Digital arrest calls', sprite: 'skull' }, { label: 'Work from home jobs', sprite: 'phone' },
  { label: 'Cashback and refunds', sprite: 'bolt' }, { label: 'Lottery wins', sprite: 'heart' }, { label: 'Parcel and customs fees', sprite: 'lock' },
  { label: 'Crypto returns', sprite: 'bubble' }, { label: 'Sextortion threats', sprite: 'eye' },
];

/** The one marquee on the landing page: breadth of scam types the analyzer recognises. Pauses on hover and stops under reduced motion. */
export function Marquee() {
  const row = [...ITEMS, ...ITEMS];
  return (
    <div className="group relative overflow-hidden border-y border-line bg-surface-1/60 py-5" aria-label="Scam types Sentinel recognises">
      <div className="flex w-max animate-marquee gap-10 pr-10 group-hover:[animation-play-state:paused]">
        {row.map((it, i) => (
          <span key={i} className="flex items-center gap-3 whitespace-nowrap text-[15px] text-bone/80" aria-hidden={i >= ITEMS.length}>
            <Sprite name={it.sprite} size={26} />{it.label}
          </span>
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-background to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-background to-transparent" />
    </div>
  );
}