import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { SearchForm } from '../../components/SearchForm'
import { formatDate, formatMoney } from '../../format'
import { PAYMENTS_PAGE_SIZE, usePayments } from '../payees/queries'

export function PaymentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const q = searchParams.get('q') ?? ''
  const page = Math.max(1, Number(searchParams.get('page')) || 1)
  const [draft, setDraft] = useState(q)
  const payments = usePayments(q, page)

  function go(changes: { q?: string; page?: number }) {
    const next = new URLSearchParams(searchParams)
    if (changes.q !== undefined) {
      if (changes.q) next.set('q', changes.q)
      else next.delete('q')
      next.delete('page')
    }
    if (changes.page !== undefined) {
      if (changes.page > 1) next.set('page', String(changes.page))
      else next.delete('page')
    }
    setSearchParams(next)
  }

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    go({ q: draft.trim() })
  }

  const count = payments.data?.count ?? 0
  const totalPages = Math.max(1, Math.ceil(count / PAYMENTS_PAGE_SIZE))
  const rows = payments.data?.results ?? []
  const first = (page - 1) * PAYMENTS_PAGE_SIZE + 1

  return (
    <div>
      <PageHeader title="Payments" description="Money received from payees, newest first.">
        <Link to="/payments/new" className={buttonPrimary}>
          Add payment
        </Link>
      </PageHeader>

      <SearchForm
        id="payment-search"
        label="Search payments"
        placeholder="Search by payee name…"
        value={draft}
        onChange={setDraft}
        onSubmit={handleSearch}
        onClear={q ? () => {
              setDraft('')
              go({ q: '' })
            } : undefined}
        className="mb-6"
      />

      {payments.isPending && <Loading>Loading payments…</Loading>}
      {payments.isError && <ErrorMessage>Couldn't load payments: {payments.error.message}</ErrorMessage>}

      {payments.data && (
        <>
          <div className="card overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Payee</th>
                  <th>Date</th>
                  <th className="text-right">Amount</th>
                  <th>Reference</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((payment) => (
                  <tr key={payment.id}>
                    <td>
                      <Link to={`/payees/${payment.payee}`} className="font-medium text-slate-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        {payment.payee_name}
                      </Link>
                    </td>
                    <td>{formatDate(payment.payment_date)}</td>
                    <td className="text-right font-medium text-green-600 dark:text-green-400">+{formatMoney(Number(payment.amount))}</td>
                    <td>{payment.payment_reference || '—'}</td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="empty">
                      {q ? 'No payments match that search' : 'No payments yet'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {count > 0 && (
            <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm muted">
                Showing {first}–{first + rows.length - 1} of {count}
              </p>
              {totalPages > 1 && (
                <div className="flex items-center gap-2">
                  <button type="button" disabled={page <= 1} onClick={() => go({ page: page - 1 })} className={buttonSecondary}>
                    Previous
                  </button>
                  <span className="px-2 text-sm muted">
                    Page {page} of {totalPages}
                  </span>
                  <button type="button" disabled={page >= totalPages} onClick={() => go({ page: page + 1 })} className={buttonSecondary}>
                    Next
                  </button>
                </div>
              )}
            </nav>
          )}
        </>
      )}
    </div>
  )
}
