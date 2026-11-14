import {
  BarController,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Legend,
  LinearScale,
  LineController,
  LineElement,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from 'chart.js'
import { Chart } from 'react-chartjs-2'

import type { TrendChart } from '../../api/types'
import { Delta } from '../../components/stats'
import { bucketLabel, formatValue } from './trendFormat'

// Register only what these charts use, so the rest of Chart.js isn't bundled.
ChartJS.register(BarController, LineController, BarElement, LineElement, PointElement, CategoryScale, LinearScale, Tooltip, Legend)

const PALETTE = ['#3b82f6', '#f59e0b', '#ef4444', '#10b981']

export function TrendChartCard({ chart, labels, granularity, note }: { chart: TrendChart; labels: string[]; granularity: string; note?: string | null }) {
  const data: ChartData<'bar' | 'line', number[], string> = {
    labels: labels.map((label) => bucketLabel(label, granularity)),
    datasets: chart.series.map((series, index) => {
      const colour = PALETTE[index % PALETTE.length]!
      return {
        type: series.type,
        label: series.label,
        data: series.data,
        yAxisID: series.axis,
        borderColor: colour,
        backgroundColor: series.type === 'bar' ? `${colour}99` : `${colour}20`,
        borderWidth: 2,
        tension: 0.35,
        pointRadius: 2,
        pointHoverRadius: 5,
      }
    }),
  }

  const options: ChartOptions<'bar' | 'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { position: 'bottom', labels: { boxWidth: 12, usePointStyle: true } },
      tooltip: {
        callbacks: {
          label: (context) => ` ${context.dataset.label}: ${formatValue(context.parsed.y ?? 0, chart.series[context.datasetIndex]!.unit)}`,
        },
      },
    },
    scales: {
      y: { beginAtZero: true, position: 'left', grid: { color: 'rgba(128,128,128,0.12)' } },
      y1: { beginAtZero: true, position: 'right', display: chart.series.some((series) => series.axis === 'y1'), grid: { drawOnChartArea: false } },
      x: { grid: { display: false } },
    },
  }

  return (
    <section aria-labelledby={`chart-${chart.key}`} className="card p-6">
      <h2 id={`chart-${chart.key}`} className="font-semibold">
        {chart.title}
      </h2>
      {note && <p className="mt-1 text-xs muted">{note}</p>}
      <dl className="mt-4 mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {chart.series.map((series) => (
          <div key={series.key}>
            <dt className="eyebrow mb-1">{series.label}</dt>
            <dd className="text-2xl font-semibold tabular-nums">{formatValue(series.total, series.unit)}</dd>
            <dd>
              <Delta percent={series.change} period="prior period" />
            </dd>
          </div>
        ))}
      </dl>
      <div className="h-64">
        <Chart type="bar" data={data} options={options} aria-label={`${chart.title} chart`} role="img" />
      </div>
    </section>
  )
}
