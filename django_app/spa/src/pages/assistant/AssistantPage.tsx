import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'

import { ApiError } from '../../api/client'
import type { Allowance, ChatMessage } from '../../api/types'
import { PageHeader, buttonSecondary } from '../../components/ui'
import { askErrorMessage, useAsk, useConversation, useNewChat } from './useAssistant'

function allowanceText(allowance: Allowance): string {
  if (allowance.unlimited) return 'Unlimited questions'
  if (allowance.exhausted) return 'No questions left today · resets at midnight UK time'
  const plural = allowance.limit === 1 ? '' : 's'
  return `${allowance.remaining} of ${allowance.limit} question${plural} left today`
}

function Bubble({ message }: { message: ChatMessage }) {
  const mine = message.role === 'user'
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      {/* Plain text in a text node: React escapes it, so an answer can never inject HTML. */}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
          mine
            ? 'rounded-br-sm bg-blue-600 text-white'
            : 'rounded-bl-sm border border-slate-200 bg-white text-slate-800 dark:border-white/5 dark:bg-slate-800 dark:text-slate-200'
        }`}
      >
        {message.content}
      </div>
    </div>
  )
}

export function AssistantPage() {
  const conversation = useConversation()
  const ask = useAsk()
  const newChat = useNewChat()
  const [question, setQuestion] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const history = conversation.data?.history ?? []

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [history.length, ask.isPending])

  if (conversation.isPending) {
    return <p className="text-sm muted">Loading TutorHub AI…</p>
  }
  if (conversation.isError) {
    return (
      <p role="alert" className="text-sm text-red-600 dark:text-red-400">
        Couldn't load TutorHub AI: {conversation.error.message}
      </p>
    )
  }

  const { allowance, examples, max_question_length: maxLength } = conversation.data
  const blocked = allowance.exhausted

  function send() {
    const text = question.trim()
    if (!text || ask.isPending || blocked) return
    setQuestion('')
    ask.mutate(text, {
      // Give the unanswered question back, so it isn't lost.
      onError: () => setQuestion(text),
      onSettled: () => inputRef.current?.focus(),
    })
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    send()
  }

  // Enter sends, Shift+Enter adds a new line.
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      send()
    }
  }

  function pickExample(example: string) {
    setQuestion(example)
    inputRef.current?.focus()
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title="TutorHub AI"
        description="Ask about your students, sessions, payees and payments. TutorHub AI can read your data but never changes it."
      >
        {history.length > 0 && (
          <button type="button" onClick={() => newChat.mutate()} disabled={newChat.isPending || ask.isPending} className={buttonSecondary}>
            New chat
          </button>
        )}
      </PageHeader>

      {ask.isError && (
        <p
          role="alert"
          className={`alert mb-6 ${
            ask.error instanceof ApiError && ask.error.status === 429
              ? 'alert-warning'
              : 'alert-error'
          }`}
        >
          {askErrorMessage(ask.error, maxLength)}
        </p>
      )}
      {newChat.isError && (
        <p role="alert" className="mb-6 text-sm text-red-600 dark:text-red-400">
          Couldn't start a new chat. Please try again.
        </p>
      )}

      {history.length > 0 ? (
        <div className="mb-6 space-y-4" aria-live="polite">
          {history.map((message, index) => (
            <Bubble key={index} message={message} />
          ))}
          {ask.isPending && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-500 dark:border-white/5 dark:bg-slate-800 dark:text-slate-400">
                Thinking…
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      ) : (
        <div className="card mb-6 p-6">
          <p className="eyebrow mb-3">Try asking</p>
          <div className="flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => pickExample(example)}
                disabled={blocked}
                className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm text-blue-700 transition-colors hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-blue-500/20 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="card p-4">
        <label htmlFor="question" className="sr-only">
          Question
        </label>
        <textarea
          id="question"
          ref={inputRef}
          rows={3}
          maxLength={maxLength}
          autoFocus
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          readOnly={ask.isPending}
          disabled={blocked}
          placeholder={blocked ? 'Come back tomorrow for more questions.' : 'e.g. How many sessions has Lok had this term?'}
          className="input resize-none"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs muted">{allowanceText(allowance)}</p>
          <button
            type="submit"
            disabled={blocked || ask.isPending || !question.trim()}
            className="btn btn-primary"
          >
            {ask.isPending ? 'Thinking…' : 'Ask'}
          </button>
        </div>
      </form>
    </div>
  )
}
