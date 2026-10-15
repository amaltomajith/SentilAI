import { useMemo } from 'react';

/**
 * Procedural pixel art: each sprite is a 12x12 bitmap. '#' = body, 'h' = highlight, 'o' = ink detail, '.' = empty.
 * The sticker outline (bone) is computed from the silhouette, so every sprite gets the same die-cut look.
 */
export const SPRITES = {
  shield: [
    '.##########.', '.#hh#######.', '.#h########.', '.#h######o#.', '.#######o##.', '.##o###o###.', '.###o#o####.', '.####o#####.', '..########..', '...######...', '....####....', '.....##.....',
  ],
  eye: [
    '............', '............', '...######...', '.##########.', '####oooo####', '###oohhoo###', '###oooooo###', '####oooo####', '.##########.', '...######...', '............', '............',
  ],
  phone: [
    '...######...', '..########..', '..#oooooo#..', '..#oooooo#..', '..#oooooo#..', '..#oooooo#..', '..#oooooo#..', '..#oooooo#..',
    '..#oooooo#..', '..########..', '..###oo###..', '...######...',
  ],
  lock: [
    '............', '...######...', '..##....##..', '..#......#..', '..#......#..', '.##########.', '.#hh#######.', '.#h########.',
    '.#####o####.', '.####ooo###.', '.#####o####.', '.##########.',
  ],
  bubble: [
    '............', '.##########.', '#hh#########', '#h##########', '#####oo#####', '##o#oooo#o##', '#####oo#####', '############',
    '.##########.', '..###.......', '..##........', '..#.........',
  ],
  heart: [
    '............', '.####..####.', '#hh#########', '#h##########', '############', '############', '.##########.', '..########..', '...######...', '....####....', '.....##.....', '............',
  ],
  skull: [
    '............', '..########..', '.##########.', '.#h########.', '.##########.', '.##oo##oo##.', '.##oo##oo##.', '.####oo####.', '...######...', '...#.##.#...', '...######...', '............',
  ],
  bolt: [
    '......###...', '.....###....', '....###.....', '...####.....', '..#######...', '.#########..', '......###...', '.....###....',
    '....###.....', '...##.......', '..##........', '..#.........',
  ],
} as const;

export type SpriteName = keyof typeof SPRITES;

const FILL: Record<string, string> = { '#': 'hsl(143 62% 50%)', h: 'hsl(143 80% 78%)', o: 'hsl(150 70% 8%)' };
const OUTLINE = 'hsl(138 16% 92%)';

function cells(rows: readonly string[]) {
  const w = 12, h = rows.length;
  const on = (x: number, y: number) => x >= 0 && y >= 0 && x < w && y < h && rows[y][x] !== '.' && rows[y][x] !== undefined;
  const out: { x: number; y: number; c: string }[] = [];
  for (let y = -1; y <= h; y++) for (let x = -1; x <= w; x++) {
    if (on(x, y)) { out.push({ x, y, c: FILL[rows[y][x]] ?? FILL['#'] }); continue; }
    let near = false;
    for (let dy = -1; dy <= 1 && !near; dy++) for (let dx = -1; dx <= 1; dx++) if (on(x + dx, y + dy)) { near = true; break; }
    if (near) out.push({ x, y, c: OUTLINE });
  }
  return out;
}

/** Decorative sticker. Pass `tilt` (deg) for the scattered look; purely visual, hidden from assistive tech. */
export function Sprite({ name, size = 48, tilt = 0, className = '' }: { name: SpriteName; size?: number; tilt?: number; className?: string }) {
  const px = useMemo(() => cells(SPRITES[name]), [name]);
  return (
    <svg aria-hidden viewBox="-1 -1 14 14" width={size} height={size} shapeRendering="crispEdges" className={className} style={{ transform: `rotate(${tilt}deg)` }}>
      {px.map((p, i) => <rect key={i} x={p.x} y={p.y} width="1.02" height="1.02" fill={p.c} />)}
    </svg>
  );
}