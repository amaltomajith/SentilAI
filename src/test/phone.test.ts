import { describe, expect, it } from 'vitest';
import { normalizeNumber, validNumber } from '@/lib/phone';

describe('normalizeNumber (mirrors backend)', () => {
  it('assumes +91 for a bare Indian mobile', () => expect(normalizeNumber('98765 43210')).toEqual({ number: '919876543210', assumed91: true }));
  it('keeps an explicit country code', () => expect(normalizeNumber('+91 98765 43211')).toEqual({ number: '919876543211', assumed91: false }));
  it('handles 00 international prefix', () => expect(normalizeNumber('0091 98765 43212').number).toBe('919876543212'));
  it('does not guess for other lengths', () => { expect(normalizeNumber('+1 415 555 0100').number).toBe('14155550100'); expect(validNumber('12345')).toBe(false); });
});
