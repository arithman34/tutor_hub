/**
 * Things only a real browser does: leaving the app for another site, and
 * saving a file. They live here so tests can mock this module (jsdom can do
 * neither).
 */

/** Send the whole page somewhere else, such as Google's consent screen. */
export function leaveFor(url: string) {
  window.location.assign(url)
}

/** Offer `blob` to the user as a download called `filename`. */
export function saveFile(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  // Free the blob once the download has had a moment to start (revoking in
  // the same tick can cancel it in some browsers).
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
