/**
 * What TutorHub's Zoom integration did to a session (ZoomMeetingEvent.Outcome
 * on the server). An empty string means it matched the session before
 * outcomes were recorded; null means Zoom never touched it.
 */
export type ZoomOutcome = 'logged' | 'no_show' | 'notes_filled' | 'linked' | ''

const LABELS: Record<ZoomOutcome, string> = {
  logged: 'Logged automatically from Zoom',
  no_show: 'Logged as a no-show from Zoom (only you joined)',
  notes_filled: 'Notes filled from Zoom',
  linked: 'Matched to its Zoom meeting; your notes were kept',
  '': 'Matched to its Zoom meeting',
}

/** A sentence for the session page and tooltips. */
export function zoomOutcomeLabel(outcome: string): string {
  return LABELS[outcome as ZoomOutcome] ?? LABELS['']
}

const SHORT: Record<ZoomOutcome, string> = {
  logged: 'Logged',
  no_show: 'No-show logged',
  notes_filled: 'Notes filled',
  linked: 'Linked, your notes kept',
  '': 'Matched',
}

/**
 * Whether a logged session was logged by hand rather than created by the Zoom
 * integration. Zoom filling or linking a session doesn't change who logged it.
 * A blank outcome predates outcomes being recorded, so it's unknown: not manual.
 */
export function isManualLog(outcome: string | null): boolean {
  return outcome === null || outcome === 'notes_filled' || outcome === 'linked'
}

/** A few words for the sweep result list. */
export function zoomOutcomeShort(outcome: string): string {
  return SHORT[outcome as ZoomOutcome] ?? SHORT['']
}
