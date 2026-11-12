/**
 * TutorHub AI's data: the conversation (a query) and asking / starting over
 * (mutations).
 *
 * Asking is an *optimistic update*: the question appears in the chat straight
 * away, before the server has answered. If the request fails, the chat is
 * rolled back to how it was; when it succeeds, the server's copy of the
 * conversation (question + answer) replaces the optimistic one.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api, unwrap } from '../../api/client'
import type { Allowance, Conversation } from '../../api/types'

export const conversationKey = ['assistant', 'conversation'] as const

export function useConversation() {
  return useQuery({
    queryKey: conversationKey,
    queryFn: async () => unwrap(await api.GET('/api/v1/assistant/')),
  })
}

/** What to tell the user when a question couldn't be answered. */
export function askErrorMessage(error: unknown, maxLength: number): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "You've reached today's TutorHub AI limit. It resets at midnight UK time."
    if (error.status === 502) return "TutorHub AI couldn't answer just now. Your question wasn't counted, so please try again."
    if (error.status === 400) return `Questions can be at most ${maxLength} characters.`
  }
  return 'Something went wrong sending your question. Please try again.'
}

function allowanceFrom(error: unknown): Allowance | null {
  if (!(error instanceof ApiError) || error.status !== 429) return null
  const body = error.body as { allowance?: Allowance } | null
  return body?.allowance ?? null
}

export function useAsk() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (question: string) => unwrap(await api.POST('/api/v1/assistant/ask', { body: { question } })),

    onMutate: async (question) => {
      // Stop any in-flight refetch from overwriting the optimistic message.
      await queryClient.cancelQueries({ queryKey: conversationKey })
      const previous = queryClient.getQueryData<Conversation>(conversationKey)
      if (previous) {
        queryClient.setQueryData<Conversation>(conversationKey, {
          ...previous,
          history: [...previous.history, { role: 'user', content: question }],
        })
      }
      // Whatever this returns is handed to onError, for the rollback.
      return { previous }
    },

    onError: (error, _question, context) => {
      if (!context?.previous) return
      // Put the chat back, but show the latest allowance if the server sent one.
      const allowance = allowanceFrom(error)
      queryClient.setQueryData<Conversation>(conversationKey, {
        ...context.previous,
        ...(allowance && { allowance }),
      })
    },

    onSuccess: (answer) => {
      queryClient.setQueryData<Conversation>(conversationKey, (current) =>
        current ? { ...current, history: answer.history, allowance: answer.allowance } : current,
      )
    },
  })
}

export function useNewChat() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      unwrap(await api.POST('/api/v1/assistant/reset'))
    },
    onSuccess: () => {
      queryClient.setQueryData<Conversation>(conversationKey, (current) => (current ? { ...current, history: [] } : current))
    },
  })
}
