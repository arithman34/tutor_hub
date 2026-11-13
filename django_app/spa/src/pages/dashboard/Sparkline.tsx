/**
 * A tiny line of `values` that stretches to fill its box. Decorative: the
 * figures it shows are on the card, so it's hidden from screen readers.
 */
export function Sparkline({ values, className = '' }: { values: number[]; className?: string }) {
  if (values.length < 2) return null
  // Drawn in a 100 x 40 box and stretched; the stroke keeps its width regardless.
  const max = Math.max(...values) || 1
  const step = 100 / (values.length - 1)
  const line = values.map((value, index) => `${(index * step).toFixed(2)},${(38 - (value / max) * 34).toFixed(2)}`).join(' ')

  return (
    <svg viewBox="0 0 100 40" preserveAspectRatio="none" aria-hidden="true" className={`text-blue-500 dark:text-blue-400 ${className}`}>
      <polygon points={`0,40 ${line} 100,40`} className="fill-current opacity-10" />
      <polyline points={line} fill="none" stroke="currentColor" strokeWidth={2} strokeLinejoin="round" vectorEffect="non-scaling-stroke" className="opacity-70" />
    </svg>
  )
}
