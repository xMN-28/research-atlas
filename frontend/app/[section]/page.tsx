import { notFound } from 'next/navigation';
import Platform from '@/components/platform';
export function generateStaticParams() { return ['literature', 'topics', 'trends', 'network', 'gaps', 'evaluation'].map(section => ({ section })); }
export default async function Page({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  if (!['literature', 'topics', 'trends', 'network', 'gaps', 'evaluation'].includes(section)) notFound();
  return <Platform section={section} />;
}
