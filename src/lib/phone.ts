/** Mirrors backend normalize_number: digits only; a bare 10-digit Indian mobile gets the 91 prefix. */
export function normalizeNumber(raw: string): { number: string; assumed91: boolean } {
  const t = raw.trim();
  const digits = t.replace(/\D/g, '');
  const n = t.startsWith('00') ? digits.replace(/^0+/, '') : digits;
  if (n.length === 10 && '6789'.includes(n[0])) return { number: '91' + n, assumed91: true };
  return { number: n, assumed91: false };
}
export const validNumber = (n: string) => n.length >= 8 && n.length <= 15;
