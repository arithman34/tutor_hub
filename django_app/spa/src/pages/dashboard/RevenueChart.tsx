import { BarController, BarElement, CategoryScale, Chart as ChartJS, LinearScale, Tooltip, type ChartData, type ChartOptions } from 'chart.js'
import { Chart } from 'react-chartjs-2'

import type { RevenueMonth } from '../../api/types'
import { formatMoney, formatMoneyRounded } from '../../format'
import { useIsDark } from '../../theme'

// Register only what this chart uses, so the rest of Chart.js isn't bundled.
ChartJS.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip)

const BLUE = '#3b82f6'
const monthName = new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' })
const monthAndYear = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })

/** Diagonal stripes, for the month that isn't over yet. Plain colour if the canvas can't draw. */
function stripes(colour: string): CanvasPattern | string {
  const tile = document.createElement('canvas')
  tile.width = tile.height = 8
  const context = tile.getContext('2d')
  if (!context) return `${colour}66`
  context.fillStyle = `${colour}40`
  context.fillRect(0, 0, 8, 8)
  context.strokeStyle = colour
  context.lineWidth = 2
  context.beginPath()
  for (const offset of [-8, 0, 8]) {
    context.moveTo(offset, 8)
    context.lineTo(offset + 8, 0)
  }
  context.stroke()
  return context.createPattern(tile, 'repeat') ?? `${colour}66`
}

/**
 * Revenue for each of the last 12 months. The current month is striped, with
 * a faint bar behind it reaching the projected total.
 */
export function RevenueChart({ months, projected }: { months: RevenueMonth[]; projected: number | null }) {
  const dark = useIsDark()
  const muted = dark ? '#94a3b8' : '#64748b'
  const current = months.findIndex((month) => month.in_progress)

  const data: ChartData<'bar', (number | null)[], string> = {
    labels: months.map((month) => monthName.format(new Date(month.month))),
    datasets: [
      {
        label: 'Received',
        data: months.map((month) => month.revenue),
        backgroundColor: months.map((month) => (month.in_progress ? stripes(BLUE) : BLUE)),
        borderColor: BLUE,
        borderWidth: months.map((month) => (month.in_progress ? 1.5 : 0)),
        borderRadius: 4,
        grouped: false,
        order: 1,
      },
      {
        label: 'On track for',
        data: months.map((month, index) => (index === current && projected !== null && projected > month.revenue ? projected : null)),
        backgroundColor: dark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.10)',
        borderColor: dark ? 'rgba(148,163,184,0.45)' : 'rgba(100,116,139,0.4)',
        borderWidth: 1,
        borderRadius: 4,
        grouped: false,
        order: 2,
      },
    ],
  }

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    datasets: { bar: { maxBarThickness: 36, categoryPercentage: 0.7, barPercentage: 1 } },
    plugins: {
      legend: { display: false },
      tooltip: {
        filter: (item) => item.raw !== null,
        callbacks: {
          title: (items) => {
            const month = months[items[0]!.dataIndex]!
            return `${monthAndYear.format(new Date(month.month))}${month.in_progress ? ' (so far)' : ''}`
          },
          label: (item) => ` ${item.dataset.label}: ${formatMoney(item.parsed.y ?? 0)}`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        border: { display: false },
        grid: { color: dark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.12)' },
        ticks: { color: muted, maxTicksLimit: 5, callback: (value) => formatMoneyRounded(Number(value)) },
      },
      x: {
        border: { display: false },
        grid: { display: false },
        ticks: { color: (context) => (context.index === current ? (dark ? '#e2e8f0' : '#0f172a') : muted) },
      },
    },
  }

  return <Chart type="bar" data={data} options={options} role="img" aria-label="Revenue for each of the last 12 months" />
}
