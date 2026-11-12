import { useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, buttonDanger, buttonPrimary } from '../../components/ui'
import { useCalendarStatus, useConnectGoogle, useDisconnectGoogle } from './queries'

// Google's OAuth callback sends the browser back here with ?error=<code>.
const CALLBACK_ERRORS: Record<string, string> = {
  access_denied: 'Google access was denied. Please try connecting again.',
  invalid_state: 'The connection took too long or was tampered with. Please try connecting again.',
  token_exchange_failed: "Couldn't finish connecting to Google. Please try again.",
}

export function ConnectionsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const status = useCalendarStatus()
  const connect = useConnectGoogle()
  const disconnect = useDisconnectGoogle()

  const errorCode = searchParams.get('error')
  const callbackError = errorCode ? (CALLBACK_ERRORS[errorCode] ?? 'Connecting to Google failed. Please try again.') : null
  const justConnected = searchParams.get('connected') === '1'
  const connected = status.data?.connected

  function handleDisconnect() {
    if (!window.confirm('Disconnect Google? TutorHub will stop seeing your calendar until you connect again.')) return
    // Clear any "connected" message from the URL along with the connection.
    disconnect.mutate(undefined, { onSuccess: () => setSearchParams({}, { replace: true }) })
  }

  return (
    <div className="max-w-2xl">
      <PageHeader title="Connections" />

      <div className="mb-4 space-y-3">
        {callbackError && <ErrorMessage>{callbackError}</ErrorMessage>}
        {justConnected && connected && (
          <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
            Google connected successfully.
          </p>
        )}
        {connect.isError && <ErrorMessage>Couldn't start connecting: {connect.error.message}</ErrorMessage>}
        {disconnect.isError && <ErrorMessage>Couldn't disconnect: {disconnect.error.message}</ErrorMessage>}
      </div>

      <section aria-labelledby="google-heading" className="card flex flex-wrap items-start gap-4 p-6">
        <div className="min-w-0 flex-1">
          <h2 id="google-heading" className="font-semibold">
            Google Calendar
          </h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Schedule lessons from TutorHub and see them on the Sessions page. TutorHub only sees the Tutoring calendar it creates, not
            the rest of your calendar.
          </p>
          <div className="mt-3 text-sm">
            {status.isPending && <Loading>Checking…</Loading>}
            {status.isError && <ErrorMessage>Couldn't check the connection: {status.error.message}</ErrorMessage>}
            {status.data && (
              <span className="inline-flex items-center gap-2">
                <span aria-hidden="true" className={`h-2 w-2 rounded-full ${connected ? 'bg-green-500' : 'bg-gray-400'}`} />
                {connected ? 'Connected' : 'Not connected'}
              </span>
            )}
          </div>
        </div>
        {status.data &&
          (connected ? (
            <button type="button" onClick={handleDisconnect} disabled={disconnect.isPending} className={buttonDanger}>
              {disconnect.isPending ? 'Disconnecting…' : 'Disconnect'}
            </button>
          ) : (
            // Stays "Opening Google…" after success too, while the browser leaves for Google.
            <button type="button" onClick={() => connect.mutate()} disabled={connect.isPending || connect.isSuccess} className={buttonPrimary}>
              {connect.isPending || connect.isSuccess ? 'Opening Google…' : 'Connect'}
            </button>
          ))}
      </section>
    </div>
  )
}
