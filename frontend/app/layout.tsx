import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {
  title: 'Research Atlas · Scientific Literature Intelligence',
  description: 'Explore 10,000 AI research papers, learned topics, temporal trends and evidence-backed research hypotheses.',
};
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" suppressHydrationWarning><body>{children}</body></html>;
}
