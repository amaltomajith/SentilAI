import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.stubGlobal('matchMedia', (q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener: () => undefined, removeEventListener: () => undefined, addListener: () => undefined, removeListener: () => undefined, onchange: null, dispatchEvent: () => false }));
vi.stubGlobal('IntersectionObserver', class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } });

import Landing from '@/pages/Landing';
import NotFound from '@/pages/NotFound';
import { AuthProvider } from '@/lib/auth';

const wrap = (ui: React.ReactNode) => render(<MemoryRouter><AuthProvider>{ui}</AuthProvider></MemoryRouter>);

describe('pages render', () => {
  it('landing shows the promise, one primary action label, and no dash characters in visible copy', () => {
    const { container } = wrap(<Landing />);
    expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/chase\s*a ghost/);
    expect(screen.getAllByText(/Get started/).length).toBeGreaterThan(0);
    expect(container.textContent ?? '').not.toMatch(/[\u2013\u2014]/);          // house rule: no em or en dashes in copy
    expect(screen.getAllByRole('img', { hidden: true }).length).toBeGreaterThan(0);
  });

  it('landing has exactly one marquee and the four step headings', () => {
    const { container } = wrap(<Landing />);
    expect(container.querySelectorAll('.animate-marquee').length).toBe(1);
    for (const h of ['Tell it who you are', 'Rehearse on a sample scam', 'Link WhatsApp, name one number', 'Watch it work, keep the proof']) expect(screen.getAllByText(h).length).toBeGreaterThan(0);
  });

  it('404 page offers a way home', () => {
    wrap(<NotFound />);
    expect(screen.getByRole('link', { name: /back to sentinel/i })).toBeTruthy();
  });
});