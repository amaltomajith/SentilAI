import { describe, expect, it } from 'vitest';
import { SPRITES } from '@/components/pixel/Sprite';

describe('pixel sprites', () => {
  it('every sprite is a 12x12 bitmap using only known cells', () => {
    for (const [name, rows] of Object.entries(SPRITES)) {
      expect(rows.length, name).toBe(12);
      for (const r of rows) { expect(r.length, `${name}: "${r}"`).toBe(12); expect(r).toMatch(/^[.#ho]+$/); }
    }
  });
});