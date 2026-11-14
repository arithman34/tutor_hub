import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { Payee } from '../../api/types'
import { applyServerErrors } from '../../components/formHelpers'
import { ErrorMessage, Loading, PageHeader, StatusBadge, buttonPrimary } from '../../components/ui'
import { balanceTone, formatBalance, formatDate, formatMoney } from '../../format'
import { PayeeFields } from './PayeeFields'
import { fromPayee, payeeFormFields, payeeFormSchema, toPayeeRequest, type PayeeFormValues } from './payeeForm'
import { usePayee, usePayeePayments, usePayeeStudents, useUpdatePayee } from './queries'

export function PayeeDetailPage() {
  const { payeeId = '' } = useParams()
  const payee = usePayee(payeeId)

  if (payee.isPending) return <Loading>Loading payee…</Loading>
  if (payee.isError) {
    const missing = payee.error instanceof ApiError && payee.error.status === 404
    return (
      <div>
        <PageHeader title="Payee" backTo="/payees" />
        <ErrorMessage>{missing ? 'That payee doesn’t exist.' : `Couldn't load the payee: ${payee.error.message}`}</ErrorMessage>
      </div>
    )
  }
  return <PayeeDetail key={payee.data.id} payee={payee.data} />
}

function balanceExplanation(balance: number): string {
  if (balance > 0) return 'In credit: they have paid more than the sessions billed.'
  if (balance < 0) return 'Owes money: the sessions billed are more than the payments received.'
  return 'Fully settled.'
}

function PayeeDetail({ payee }: { payee: Payee }) {
  const update = useUpdatePayee(payee.id)
  const students = usePayeeStudents(payee.id)
  const payments = usePayeePayments(payee.id)
  const [formError, setFormError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const form = useForm<PayeeFormValues>({ resolver: zodResolver(payeeFormSchema), defaultValues: fromPayee(payee) })

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    setSaved(false)
    update.mutate(toPayeeRequest(values), {
      onSuccess: (updated) => {
        form.reset(fromPayee(updated))
        setSaved(true)
      },
      onError: (error) => setFormError(applyServerErrors(error, form.setError, payeeFormFields)),
    })
  })

  const borderTone = payee.balance < 0 ? 'border-red-200 dark:border-red-900' : payee.balance > 0 ? 'border-green-200 dark:border-green-900' : 'border-slate-200 dark:border-white/5'

  return (
    <div>
      <PageHeader title={`${payee.first_name} ${payee.last_name}`} backTo="/payees" />

      <section aria-label="Balance" className={`mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-5 dark:bg-slate-800 ${borderTone}`}>
        <div>
          <p className="text-sm muted">Current balance</p>
          <p className={`mt-0.5 text-3xl font-bold ${balanceTone(payee.balance)}`}>{formatBalance(payee.balance)}</p>
        </div>
        <p className="max-w-xs text-sm muted sm:text-right">{balanceExplanation(payee.balance)}</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card lg:col-span-1">
          <div className="card-header">
            <div className="min-w-0">
              <h2 className="section-title">Payee info</h2>
            </div>
          </div>
          <div className="p-5">
          <form onSubmit={onSubmit} noValidate className="space-y-4">
            {formError && <ErrorMessage>{formError}</ErrorMessage>}
            <PayeeFields form={form} />
            <button type="submit" disabled={update.isPending || !form.formState.isDirty} className={`${buttonPrimary} w-full`}>
              {update.isPending ? 'Saving…' : 'Save changes'}
            </button>
            {saved && !form.formState.isDirty && (
              <p role="status" className="text-center text-xs text-green-600 dark:text-green-400">
                Saved
              </p>
            )}
          </form>
          </div>
        </section>

        <section className="card lg:col-span-2">
          <div className="card-header">
            <h2 className="section-title">Linked students</h2>
          </div>
          {students.isPending && <div className="p-6"><Loading>Loading students…</Loading></div>}
          {students.isError && <div className="p-6"><ErrorMessage>Couldn't load students.</ErrorMessage></div>}
          {students.data && (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Level</th>
                  <th>Hourly rate</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {students.data.map((student) => (
                  <tr key={student.id}>
                    <td>
                      <Link to={`/students/${student.id}`} className="font-medium text-slate-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        {student.first_name} {student.last_name}
                      </Link>
                    </td>
                    <td>{student.level || '—'}</td>
                    <td>{student.hourly_rate ? formatMoney(student.hourly_rate) : '—'}</td>
                    <td>
                      <StatusBadge active={student.is_active} />
                    </td>
                  </tr>
                ))}
                {students.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="empty">
                      No students linked
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </section>
      </div>

      <section className="card mt-6">
        <div className="card-header">
          <h2 className="section-title">Payment history</h2>
          <Link to={`/payments/new?payee_id=${payee.id}`} className={`${buttonPrimary} py-1.5`}>
            Add payment
          </Link>
        </div>
        {payments.isPending && <div className="p-6"><Loading>Loading payments…</Loading></div>}
        {payments.isError && <div className="p-6"><ErrorMessage>Couldn't load payments.</ErrorMessage></div>}
        {payments.data && (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Reference</th>
                  <th className="text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {payments.data.results.map((payment) => (
                  <tr key={payment.id}>
                    <td>{formatDate(payment.payment_date)}</td>
                    <td className="font-mono text-xs text-slate-400">{payment.payment_reference || '—'}</td>
                    <td className="text-right font-medium text-green-600 dark:text-green-400">+{formatMoney(Number(payment.amount))}</td>
                  </tr>
                ))}
                {payments.data.results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="empty">
                      No payments recorded
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {payments.data.count > payments.data.results.length && (
              <p className="px-6 py-3 text-xs muted">
                Showing the latest {payments.data.results.length} of {payments.data.count} payments.
              </p>
            )}
          </>
        )}
      </section>
    </div>
  )
}
