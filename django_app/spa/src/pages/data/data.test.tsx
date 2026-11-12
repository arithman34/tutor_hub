import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { saveFile } from '../../browser'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'

vi.mock('../../browser')

beforeEach(() => vi.mocked(saveFile).mockClear())

function exportFile() {
  return new File(['{"version": 1}'], 'tutorhub_export.json', { type: 'application/json' })
}

describe('my data page', () => {
  it('downloads the export under the name the server gives it', async () => {
    server.use(
      http.get('*/api/v1/data/export', () =>
        HttpResponse.json(
          { version: 1, students: [] },
          { headers: { 'Content-Disposition': 'attachment; filename="tutorhub_export_20261112_140000.json"' } },
        ),
      ),
    )
    const user = userEvent.setup()
    renderApp('/data')

    await user.click(await screen.findByRole('button', { name: 'Download export' }))

    await waitFor(() => expect(saveFile).toHaveBeenCalledTimes(1))
    const [blob, filename] = vi.mocked(saveFile).mock.calls[0]!
    expect(filename).toBe('tutorhub_export_20261112_140000.json')
    expect(JSON.parse(await blob.text())).toEqual({ version: 1, students: [] })
  })

  it('imports a file as multipart only after confirming, and reports what it loaded', async () => {
    let uploaded: File | null = null
    server.use(
      http.post('*/api/v1/data/import', async ({ request }) => {
        uploaded = (await request.formData()).get('file') as File
        return HttpResponse.json({ payees: 2, students: 1, sessions: 40, payments: 12 })
      }),
    )
    const confirm = vi.spyOn(window, 'confirm').mockReturnValueOnce(false).mockReturnValueOnce(true)
    const user = userEvent.setup()
    renderApp('/data')

    const importButton = await screen.findByRole('button', { name: 'Import' })
    expect(importButton).toBeDisabled()
    await user.upload(screen.getByLabelText('Export file'), exportFile())

    await user.click(importButton)
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('deletes all of your students'))
    expect(uploaded).toBeNull()

    await user.click(importButton)
    expect(await screen.findByRole('status')).toHaveTextContent('Import complete: 1 student, 2 payees, 40 sessions and 12 payments.')
    expect(await uploaded!.text()).toBe('{"version": 1}')
  })

  it('shows why an import was refused', async () => {
    server.use(http.post('*/api/v1/data/import', () => HttpResponse.json({ detail: "Import failed: The file isn't a TutorHub export." }, { status: 400 })))
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    renderApp('/data')

    await user.upload(await screen.findByLabelText('Export file'), exportFile())
    await user.click(screen.getByRole('button', { name: 'Import' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("Import failed: The file isn't a TutorHub export.")
  })
})
