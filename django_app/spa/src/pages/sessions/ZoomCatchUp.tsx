import { useIsDemo } from '../../auth'
import { buttonSecondary } from '../../components/ui'
import { useZoomStatus } from '../connections/queries'
import { useZoomSweep } from './queries'

function plural(count: number, word: string) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

/** What a sweep did, in words. */
function describeSweep({ logged, updated, waiting, failed }: { logged: number; updated: number; waiting: number; failed: number }) {
  const parts = []
  if (logged) parts.push(`logged ${plural(logged, 'lesson')}`)
  if (updated) parts.push(`added notes to ${plural(updated, 'session')}`)
  if (waiting) parts.push(`${plural(waiting, 'lesson')} still waiting for Zoom`)
  if (failed) parts.push(`${plural(failed, 'lesson')} couldn't be logged`)
  return parts.length ? `Zoom: ${parts.join(', ')}.` : 'Zoom: nothing new to log.'
}

/**
 * Lessons are logged automatically when Zoom says a summary is ready. This is
 * the manual catch-up, for anything missed (or a no-show Zoom never summarised).
 */
export function ZoomCatchUp() {
  const isDemo = useIsDemo()
  const zoom = useZoomStatus({ enabled: !isDemo })
  const sweep = useZoomSweep()

  if (isDemo || !zoom.data?.connected) return null

  return (
    <>
      {sweep.isSuccess && (
        <span role="status" className="text-sm text-gray-600 dark:text-gray-300">
          {describeSweep(sweep.data)}
        </span>
      )}
      {sweep.isError && (
        <span role="alert" className="text-sm text-red-600 dark:text-red-400">
          {sweep.error.message}
        </span>
      )}
      <button type="button" onClick={() => sweep.mutate()} disabled={sweep.isPending} className={buttonSecondary}>
        {sweep.isPending ? 'Checking Zoom…' : 'Check Zoom for missed lessons'}
      </button>
    </>
  )
}
