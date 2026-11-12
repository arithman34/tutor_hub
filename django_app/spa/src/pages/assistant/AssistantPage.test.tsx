import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'

import type { Allowance, ChatMessage, Conversation } from '../../api/types'
import { renderApp } from '../../test/render'
import { server } from '../../test/server'

const allowance = (used: number, limit: number | null = 5): Allowance => ({
  limit,
  used,
  remaining: limit === null ? null : Math.max(limit - used, 0),
  unlimited: limit === null,
  exhausted: limit !== null && used >= limit,
})

function conversation(history: ChatMessage[] = [], used = 0, limit: number | null = 5): Conversation {
  return {
    history,
    allowance: allowance(used, limit),
    examples: ['Does any payee owe me money?', 'How many sessions did I teach last month?'],
    max_question_length: 1000,
  }
}

/** Serves `initial` from GET, and lets each test decide how /ask answers. */
function serveConversation(initial: Conversation) {
  server.use(http.get('*/api/v1/assistant/', () => HttpResponse.json(initial)))
}

beforeEach(() => serveConversation(conversation()))

describe('TutorHub AI page', () => {
  it('suggests example questions and shows the allowance', async () => {
    const user = userEvent.setup()
    renderApp('/assistant')

    await user.click(await screen.findByRole('button', { name: 'Does any payee owe me money?' }))

    expect(screen.getByLabelText('Question')).toHaveValue('Does any payee owe me money?')
    expect(screen.getByText('5 of 5 questions left today')).toBeInTheDocument()
  })

  it('shows the question straight away, then the answer', async () => {
    let release!: () => void
    const answered = new Promise<void>((resolve) => (release = resolve))
    let sent: unknown = null
    server.use(
      http.post('*/api/v1/assistant/ask', async ({ request }) => {
        sent = await request.json()
        await answered
        return HttpResponse.json({
          reply: 'You taught 4 sessions.',
          history: [
            { role: 'user', content: 'How many sessions?' },
            { role: 'assistant', content: 'You taught 4 sessions.' },
          ],
          allowance: allowance(1),
        })
      }),
    )
    const user = userEvent.setup()
    renderApp('/assistant')

    await user.type(await screen.findByLabelText('Question'), 'How many sessions?')
    await user.click(screen.getByRole('button', { name: 'Ask' }))

    // Optimistic: the question and a placeholder are on screen before the server answers.
    expect(await screen.findByText('How many sessions?')).toBeInTheDocument()
    expect(screen.getAllByText('Thinking…').length).toBeGreaterThan(0)
    expect(screen.getByLabelText('Question')).toHaveValue('')

    release()

    expect(await screen.findByText('You taught 4 sessions.')).toBeInTheDocument()
    expect(screen.queryByText('Thinking…')).not.toBeInTheDocument()
    expect(screen.getByText('4 of 5 questions left today')).toBeInTheDocument()
    expect(sent).toEqual({ question: 'How many sessions?' })
  })

  it('sends on Enter but not on Shift+Enter', async () => {
    let asks = 0
    server.use(
      http.post('*/api/v1/assistant/ask', () => {
        asks++
        return HttpResponse.json({ reply: 'Hi', history: [], allowance: allowance(1) })
      }),
    )
    const user = userEvent.setup()
    renderApp('/assistant')
    const box = await screen.findByLabelText('Question')

    await user.type(box, 'line one{Shift>}{Enter}{/Shift}line two')
    expect(box).toHaveValue('line one\nline two')
    expect(asks).toBe(0)

    await user.keyboard('{Enter}')
    await waitFor(() => expect(asks).toBe(1))
  })

  it('rolls back and keeps the question when the daily limit is reached', async () => {
    server.use(
      http.post('*/api/v1/assistant/ask', () =>
        HttpResponse.json({ detail: 'Limit reached.', allowance: allowance(5) }, { status: 429 }),
      ),
    )
    const user = userEvent.setup()
    renderApp('/assistant')

    await user.type(await screen.findByLabelText('Question'), 'One more?')
    await user.click(screen.getByRole('button', { name: 'Ask' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("You've reached today's TutorHub AI limit")
    // The optimistic bubble is gone, and the text is back in the (now disabled) box.
    expect(screen.queryByText('One more?', { selector: 'div' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Question')).toHaveValue('One more?')
    expect(screen.getByLabelText('Question')).toBeDisabled()
    expect(screen.getByText('No questions left today · resets at midnight UK time')).toBeInTheDocument()
  })

  it('explains a provider failure and keeps the question', async () => {
    server.use(http.post('*/api/v1/assistant/ask', () => HttpResponse.json({ detail: 'down' }, { status: 502 })))
    const user = userEvent.setup()
    renderApp('/assistant')

    await user.type(await screen.findByLabelText('Question'), 'Who owes me?')
    await user.click(screen.getByRole('button', { name: 'Ask' }))

    expect(await screen.findByRole('alert')).toHaveTextContent("wasn't counted")
    expect(screen.getByLabelText('Question')).toHaveValue('Who owes me?')
    expect(screen.getByLabelText('Question')).toBeEnabled()
  })

  it('does nothing for a blank question', async () => {
    const user = userEvent.setup()
    renderApp('/assistant')
    await user.type(await screen.findByLabelText('Question'), '   ')
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })

  it('starts a new chat', async () => {
    serveConversation(conversation([
      { role: 'user', content: 'Hi' },
      { role: 'assistant', content: 'Hello!' },
    ]))
    let reset = false
    server.use(
      http.post('*/api/v1/assistant/reset', () => {
        reset = true
        return new HttpResponse(null, { status: 204 })
      }),
    )
    const user = userEvent.setup()
    renderApp('/assistant')

    await user.click(await screen.findByRole('button', { name: 'New chat' }))

    expect(await screen.findByText('Try asking')).toBeInTheDocument()
    expect(screen.queryByText('Hello!')).not.toBeInTheDocument()
    expect(reset).toBe(true)
  })

  it('locks the form when today’s questions are used up', async () => {
    serveConversation(conversation([], 1, 1))
    renderApp('/assistant')

    expect(await screen.findByLabelText('Question')).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Does any payee owe me money?' })).toBeDisabled()
  })

  it('says unlimited when there is no limit', async () => {
    serveConversation(conversation([], 3, null))
    renderApp('/assistant')
    expect(await screen.findByText('Unlimited questions')).toBeInTheDocument()
  })

  it('shows answers as text, never as HTML', async () => {
    serveConversation(conversation([
      { role: 'user', content: 'Hi' },
      { role: 'assistant', content: '<img src=x onerror="alert(1)">' },
    ]))
    const { container } = renderApp('/assistant')

    expect(await screen.findByText('<img src=x onerror="alert(1)">')).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
  })

  it('is reached from the sidebar without leaving the app', async () => {
    renderApp('/')
    const sidebar = await screen.findByRole('complementary', { name: 'Sidebar' })
    expect(within(sidebar).getByRole('link', { name: 'TutorHub AI' })).toHaveAttribute('href', '/assistant')
  })
})
