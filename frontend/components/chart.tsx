'use client';
import dynamic from 'next/dynamic';
import type { Data, Layout } from 'plotly.js';
const Plot = dynamic(() => import('./plot-client'), { ssr: false, loading: () => <div className="chart-loading">Preparing visualization…</div> });
export const COLORS = ['#568770', '#ca925b', '#7886b5', '#b66f83', '#63a8b1', '#a2a761', '#9779b0', '#648caa', '#c07756', '#83917c'];
export default function Chart({ data, layout = {}, height = 320, dark = false }: { data: Data[]; layout?: Partial<Layout>; height?: number; dark?: boolean }) {
  return <Plot data={data} layout={{ autosize: true, height, paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
    font: { family: 'Cabinet Grotesk, Segoe UI, sans-serif', color: dark ? '#c5c9c6' : '#6c746e', size: 11 },
    margin: { t: 20, l: 50, r: 20, b: 45 }, hovermode: 'closest',
    xaxis: { gridcolor: dark ? '#2b3932' : '#edf0eb', zeroline: false },
    yaxis: { gridcolor: dark ? '#2b3932' : '#edf0eb', zeroline: false },
    legend: { orientation: 'h', y: -0.18 }, ...layout }}
    config={{ displaylogo: false, responsive: true, modeBarButtonsToRemove: ['lasso2d', 'select2d'], toImageButtonOptions: { format: 'png', filename: 'research-atlas' } }}
    useResizeHandler style={{ width: '100%' }} />;
}
