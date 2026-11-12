import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { api, unwrap } from '../../api/client'
import { saveFile } from '../../browser'
import { ErrorMessage, PageHeader, buttonDanger, buttonPrimary } from '../../components/ui'

function count(n: number, noun: string) {
  return `${n} ${noun}${n === 1 ? '' : 's'}`
}

/** The filename Django suggests in Content-Disposition, or a sensible default. */
function attachmentName(response: Response): string {
  const header = response.headers.get('Content-Disposition') ?? ''
  return /filename="?([^";]+)"?/.exec(header)?.[1] ?? 'tutorhub_export.json'
}

function useExport() {
  return useMutation({
    mutationFn: async () => {
      // Fetched through the API client rather than a plain link, so an expired
      // login is refreshed instead of downloading an error page.
      const result = await api.GET('/api/v1/data/export', { parseAs: 'blob' })
      saveFile(unwrap(result) as Blob, attachmentName(result.response))
    },
  })
}

function useImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('file', file, file.name)
      return unwrap(
        await api.POST('/api/v1/data/import', {
          // The schema types the upload as a binary string, which `body` must
          // match; what's actually sent is the multipart form with the file.
          body: { file: file.name },
          bodySerializer: () => form,
        }),
      )
    },
    // Every page's data has just been replaced, so refetch all of it.
    onSuccess: () => queryClient.invalidateQueries(),
  })
}

export function MyDataPage() {
  const exportData = useExport()
  const importData = useImport()
  const [file, setFile] = useState<File | null>(null)

  function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    const confirmed = window.confirm(
      'This deletes all of your students, payees, sessions and payments and replaces them with the file. Are you sure?',
    )
    if (confirmed) importData.mutate(file)
  }

  const counts = importData.data

  return (
    <div className="max-w-2xl space-y-5">
      <PageHeader title="My Data" />

      <section aria-labelledby="export-heading" className="card p-6">
        <h2 id="export-heading" className="font-semibold">
          Export
        </h2>
        <p className="mt-1 mb-4 text-sm text-gray-500 dark:text-gray-400">
          Downloads your students, payees, sessions and payments as a single JSON file. Your account details and password aren't
          included.
        </p>
        {exportData.isError && (
          <div className="mb-4">
            <ErrorMessage>Couldn't export: {exportData.error.message}</ErrorMessage>
          </div>
        )}
        <button type="button" onClick={() => exportData.mutate()} disabled={exportData.isPending} className={buttonPrimary}>
          {exportData.isPending ? 'Preparing…' : 'Download export'}
        </button>
      </section>

      <section aria-labelledby="import-heading" className="card p-6">
        <h2 id="import-heading" className="font-semibold">
          Import
        </h2>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Upload a file exported from TutorHub.{' '}
          <strong className="font-semibold text-red-600 dark:text-red-400">
            This permanently deletes your existing students, payees, sessions and payments
          </strong>{' '}
          and replaces them with the file's contents. If anything in the file is wrong, nothing changes.
        </p>

        <div className="my-4 space-y-3">
          {importData.isError && <ErrorMessage>{importData.error.message}</ErrorMessage>}
          {counts && (
            <p role="status" className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-700 dark:border-green-800 dark:bg-green-900/20 dark:text-green-400">
              Import complete: {count(counts.students, 'student')}, {count(counts.payees, 'payee')}, {count(counts.sessions, 'session')}{' '}
              and {count(counts.payments, 'payment')}.
            </p>
          )}
        </div>

        <form onSubmit={handleImport} className="flex flex-wrap items-center gap-3">
          <label htmlFor="import-file" className="sr-only">
            Export file
          </label>
          <input
            id="import-file"
            type="file"
            accept=".json,application/json"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="text-sm text-gray-600 file:mr-3 file:rounded-lg file:border-0 file:bg-gray-100 file:px-3 file:py-2 file:text-sm dark:text-gray-300 dark:file:bg-gray-700 dark:file:text-gray-200"
          />
          <button type="submit" disabled={!file || importData.isPending} className={buttonDanger}>
            {importData.isPending ? 'Importing…' : 'Import'}
          </button>
        </form>
      </section>
    </div>
  )
}
