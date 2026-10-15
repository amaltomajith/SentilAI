import { describe, expect, it } from 'vitest';
import { cleanBase } from './base';

describe('cleanBase', () => {
  it('passes a plain origin through and strips trailing slashes', () => {
    expect(cleanBase('https://a.onrender.com/')).toBe('https://a.onrender.com');
  });
  it('recovers from a pasted markdown link', () => {
    expect(cleanBase('https://a.onrender.com](https://a.onrender.com)')).toBe('https://a.onrender.com');
  });
  it('is empty when unset', () => {
    expect(cleanBase(undefined)).toBe('');
  });
});
