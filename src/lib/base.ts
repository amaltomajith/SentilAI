/** API origin from the build env. Tolerates a pasted markdown link or trailing slash: "[https://x](https://x)/" becomes "https://x". */
export function cleanBase(raw: string | undefined): string {
  const m = (raw ?? '').match(/https?:\/\/[^\s\]()[]+/);
  return m ? m[0].replace(/\/+$/, '') : '';
}
export const API_BASE = cleanBase(import.meta.env.VITE_API_BASE_URL as string | undefined);