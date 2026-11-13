import type { UseMutationResult, UseQueryResult } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'

import { useIsDemo } from '../../auth'
import { ErrorMessage, Loading, PageHeader, buttonDanger, buttonPrimary } from '../../components/ui'
import {
  useCalendarStatus,
  useConnectGoogle,
  useConnectZoom,
  useDisconnectGoogle,
  useDisconnectZoom,
  useZoomStatus,
} from './queries'

type Provider = 'google' | 'zoom'

const PROVIDER_NAMES: Record<Provider, string> = { google: 'Google', zoom: 'Zoom' }

// The OAuth callbacks send the browser back here with ?error=<code>. Zoom's
// also adds ?provider=zoom; Google's predates that, so no provider means Google.
function callbackErrorMessage(code: string, name: string): string {
  switch (code) {
    case 'access_denied':
      return `${name} access was denied. Please try connecting again.`
    case 'invalid_state':
      return 'The connection took too long or was tampered with. Please try connecting again.'
    case 'token_exchange_failed':
      return `Couldn't finish connecting to ${name}. Please try again.`
    default:
      return `Connecting to ${name} failed. Please try again.`
  }
}

export function ConnectionsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const google = useCalendarStatus()
  const zoom = useZoomStatus()

  const provider: Provider = searchParams.get('provider') === 'zoom' ? 'zoom' : 'google'
  const name = PROVIDER_NAMES[provider]
  const errorCode = searchParams.get('error')
  const callbackError = errorCode ? callbackErrorMessage(errorCode, name) : null
  const justConnected = searchParams.get('connected') === '1' && (provider === 'zoom' ? zoom : google).data?.connected

  // Clear any "connected" or error message from the URL along with a connection.
  const clearMessages = () => setSearchParams({}, { replace: true })

  return (
    <div className="max-w-2xl">
      <PageHeader title="Connections" />

      <div className="mb-4 space-y-3">
        {callbackError && <ErrorMessage>{callbackError}</ErrorMessage>}
        {justConnected && (
          <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
            {name} connected successfully.
          </p>
        )}
      </div>

      <div className="space-y-4">
        <ConnectionCard
          id="google"
          title="Google Calendar"
          name="Google"
          description="Schedule lessons from TutorHub and see them on the Sessions page. TutorHub only sees the Tutoring calendar it creates, not the rest of your calendar."
          confirmDisconnect="Disconnect Google? TutorHub will stop seeing your calendar until you connect again."
          status={google}
          connect={useConnectGoogle()}
          disconnect={useDisconnectGoogle()}
          onDisconnected={clearMessages}
        />
        <ConnectionCard
          id="zoom"
          title="Zoom"
          name="Zoom"
          description="Fetch a lesson's AI Companion summary straight from Zoom to fill in its notes. TutorHub only reads past meetings and their summaries, and only when you ask."
          confirmDisconnect="Disconnect Zoom? You can still paste Zoom summaries by hand."
          status={zoom}
          connect={useConnectZoom()}
          disconnect={useDisconnectZoom()}
          onDisconnected={clearMessages}
        />
      </div>
    </div>
  )
}

function ConnectionCard({
  id,
  title,
  name,
  description,
  confirmDisconnect,
  status,
  connect,
  disconnect,
  onDisconnected,
}: {
  id: string
  title: string
  name: string
  description: string
  confirmDisconnect: string
  status: UseQueryResult<{ connected: boolean }, Error>
  connect: UseMutationResult<unknown, Error, void>
  disconnect: UseMutationResult<void, Error, void>
  onDisconnected: () => void
}) {
  const isDemo = useIsDemo()
  const connected = status.data?.connected

  function handleDisconnect() {
    if (!window.confirm(confirmDisconnect)) return
    disconnect.mutate(undefined, { onSuccess: onDisconnected })
  }

  return (
    <section aria-labelledby={`${id}-heading`} className="card flex flex-wrap items-start gap-4 p-6">
      <div className="min-w-0 flex-1">
        <h2 id={`${id}-heading`} className="font-semibold">
          {title}
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{description}</p>
        <div className="mt-3 space-y-2 text-sm">
          {status.isPending && <Loading>Checking…</Loading>}
          {status.isError && <ErrorMessage>Couldn't check the connection: {status.error.message}</ErrorMessage>}
          {status.data && (
            <span className="inline-flex items-center gap-2">
              <span aria-hidden="true" className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`} />
              {connected ? 'Connected' : 'Not connected'}
            </span>
          )}
          {connect.isError && <ErrorMessage>Couldn't start connecting: {connect.error.message}</ErrorMessage>}
          {disconnect.isError && <ErrorMessage>Couldn't disconnect: {disconnect.error.message}</ErrorMessage>}
        </div>
      </div>
      {status.data &&
        (connected ? (
          <button type="button" onClick={handleDisconnect} disabled={disconnect.isPending} className={buttonDanger}>
            {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
          </button>
        ) : isDemo ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Not available in the demo.</p>
        ) : (
          // Stays "Opening …" after success too, while the browser leaves for the provider.
          <button type="button" onClick={() => connect.mutate()} disabled={connect.isPending || connect.isSuccess} className={buttonPrimary}>
            {connect.isPending || connect.isSuccess ? `Opening ${name}…` : 'Connect'}
          </button>
        ))}
    </section>
  )
}
