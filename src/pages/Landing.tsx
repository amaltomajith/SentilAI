import { Nav } from '@/components/landing/Nav';
import { Marquee } from '@/components/landing/Marquee';
import { Hero, HowItWorks } from '@/components/landing/Sections';
import { Bento, Boundaries, Faq, FinalCta, Footer, Measured } from '@/components/landing/Sections2';

export default function Landing() {
  return (
    <div className="min-h-screen">
      <Nav />
      <main>
        <Hero />
        <Marquee />
        <HowItWorks />
        <Bento />
        <Boundaries />
        <Measured />
        <Faq />
        <FinalCta />
      </main>
      <Footer />
    </div>
  );
}