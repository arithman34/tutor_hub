/**
 * Payees and payments. A payee's balance depends on payments, sessions and
 * student rates, so anything that changes those calls invalidateBalances().
 */
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'
import type { Payee, PayeeRequest, PaymentRequest } from '../../api/types'

export const PAYMENTS_PAGE_SIZE = 20

export const payeeKeys = {
  all: ['payees'] as const,
  list: (q: string) => ['payees', 'list', q] as const,
  detail: (id: string) => ['payees', 'detail', id] as const,
  students: (id: string) => ['payees', 'detail', id, 'students'] as const,
}

export const paymentKeys = {
  all: ['payments'] as const,
  list: (q: string, page: number) => ['payments', 'list', q, page] as const,
  forPayee: (payeeId: string) => ['payments', 'payee', payeeId] as const,
}

/** Anything that moves money or billed hours changes balances and the dashboard. */
export function invalidateBalances(queryClient: QueryClient) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: payeeKeys.all }),
    queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
  ])
}

export function usePayees(q = '') {
  return useQuery({
    queryKey: payeeKeys.list(q),
    queryFn: async () => unwrap(await api.GET('/api/v1/payees/', { params: { query: q ? { q } : {} } })),
  })
}

export function usePayee(id: string) {
  return useQuery({
    queryKey: payeeKeys.detail(id),
    queryFn: async () => unwrap(await api.GET('/api/v1/payees/{id}/', { params: { path: { id } } })),
  })
}

export function usePayeeStudents(payeeId: string) {
  return useQuery({
    queryKey: payeeKeys.students(payeeId),
    queryFn: async () => unwrap(await api.GET('/api/v1/students/', { params: { query: { payee: payeeId } } })),
  })
}

export function usePayments(q: string, page: number) {
  return useQuery({
    queryKey: paymentKeys.list(q, page),
    queryFn: async () =>
      unwrap(
        await api.GET('/api/v1/payments/', {
          params: { query: { limit: PAYMENTS_PAGE_SIZE, offset: (page - 1) * PAYMENTS_PAGE_SIZE, ...(q && { q }) } },
        }),
      ),
    // Keep showing the current page while the next one loads.
    placeholderData: (previous) => previous,
  })
}

export function usePayeePayments(payeeId: string) {
  return useQuery({
    queryKey: paymentKeys.forPayee(payeeId),
    queryFn: async () => unwrap(await api.GET('/api/v1/payments/', { params: { query: { payee: payeeId, limit: 100 } } })),
  })
}

export function useCreatePayee() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PayeeRequest) => unwrap(await api.POST('/api/v1/payees/', { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: payeeKeys.all }),
  })
}

export function useUpdatePayee(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PayeeRequest) =>
      unwrap(await api.PATCH('/api/v1/payees/{id}/', { params: { path: { id } }, body })),
    onSuccess: (payee) => {
      queryClient.setQueryData<Payee>(payeeKeys.detail(id), payee)
      // Payment rows show the payee's name.
      return Promise.all([
        queryClient.invalidateQueries({ queryKey: ['payees', 'list'] }),
        queryClient.invalidateQueries({ queryKey: paymentKeys.all }),
      ])
    },
  })
}

export function useCreatePayment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: PaymentRequest) => unwrap(await api.POST('/api/v1/payments/', { body })),
    onSuccess: () => Promise.all([queryClient.invalidateQueries({ queryKey: paymentKeys.all }), invalidateBalances(queryClient)]),
  })
}
