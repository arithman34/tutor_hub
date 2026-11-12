import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { api, unwrap } from '../../api/client'

export const RANGES = [
  { value: '3m', label: '3M' },
  { value: '6m', label: '6M' },
  { value: '12m', label: '12M' },
  { value: 'ytd', label: 'YTD' },
  { value: 'all', label: 'All' },
] as const

export const GRANULARITIES = ['day', 'week', 'month'] as const

export type Range = (typeof RANGES)[number]['value']
export type Granularity = (typeof GRANULARITIES)[number]

export interface TrendFilters {
  range: Range
  granularity: Granularity
  start: string
  end: string
  student_id: string
  payee_id: string
}

export const DEFAULT_FILTERS: TrendFilters = { range: '12m', granularity: 'month', start: '', end: '', student_id: '', payee_id: '' }

export function useTrends(filters: TrendFilters) {
  return useQuery({
    queryKey: ['analytics', 'trends', filters],
    queryFn: async () => {
      // Leave out blank filters; explicit dates override the range on the server.
      const query = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '')) as Partial<TrendFilters>
      return unwrap(await api.GET('/api/v1/analytics/trends', { params: { query } }))
    },
    // Keep the current charts on screen while new numbers load, instead of flashing empty.
    placeholderData: keepPreviousData,
  })
}

export function useFilterOptions() {
  return useQuery({
    queryKey: ['analytics', 'filters'],
    queryFn: async () => unwrap(await api.GET('/api/v1/analytics/filters')),
  })
}
