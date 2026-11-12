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

  const borderTone = payee.balance < 0 ? 'border-red-200 dark:border-red-900' : payee.balance > 0 ? 'border-green-200 dark:border-green-900' : 'border-gray-200 dark:border-gray-700'

  return (
    <div>
      <PageHeader title={`${payee.first_name} ${payee.last_name}`} backTo="/payees" />

      <section aria-label="Balance" className={`mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white p-5 dark:bg-gray-800 ${borderTone}`}>
        <div>
          <p className="text-sm text-gray-500 dark:text-gray-400">Current balance</p>
          <p className={`mt-0.5 text-3xl font-bold ${balanceTone(payee.balance)}`}>{formatBalance(payee.balance)}</p>
        </div>
        <p className="max-w-xs text-sm text-gray-500 dark:text-gray-400 sm:text-right">{balanceExplanation(payee.balance)}</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card p-6 lg:col-span-1">
          <h2 className="mb-4 font-semibold">Payee info</h2>
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
        </section>

        <section className="card lg:col-span-2">
          <h2 className="border-b border-gray-200 px-6 py-4 font-semibold dark:border-gray-700">Linked students</h2>
          {students.isPending && <div className="p-6"><Loading>Loading students…</Loading></div>}
          {students.isError && <div className="p-6"><ErrorMessage>Couldn't load students.</ErrorMessage></div>}
          {students.data && (
            <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th className="px-6 py-3">Name</th>
                  <th className="px-6 py-3">Level</th>
                  <th className="px-6 py-3">Hourly rate</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {students.data.map((student) => (
                  <tr key={student.id} className="border-b border-gray-200 last:border-0 dark:border-gray-700">
                    <td className="px-6 py-4">
                      <Link to={`/students/${student.id}`} className="font-medium text-gray-900 hover:text-blue-600 dark:text-white dark:hover:text-blue-400">
                        {student.first_name} {student.last_name}
                      </Link>
                    </td>
                    <td className="px-6 py-4">{student.level || '—'}</td>
                    <td className="px-6 py-4">{student.hourly_rate ? formatMoney(student.hourly_rate) : '—'}</td>
                    <td className="px-6 py-4">
                      <StatusBadge active={student.is_active} />
                    </td>
                  </tr>
                ))}
                {students.data.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-6 py-8 text-center text-gray-400">
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
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
          <h2 className="font-semibold">Payment history</h2>
          <Link to={`/payments/new?payee_id=${payee.id}`} className={`${buttonPrimary} py-1.5`}>
            Add payment
          </Link>
        </div>
        {payments.isPending && <div className="p-6"><Loading>Loading payments…</Loading></div>}
        {payments.isError && <div className="p-6"><ErrorMessage>Couldn't load payments.</ErrorMessage></div>}
        {payments.data && (
          <>
            <table className="w-full text-left text-sm text-gray-600 dark:text-gray-300">
              <thead className="bg-gray-50 text-xs tracking-wider text-gray-500 uppercase dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <th className="px-6 py-3">Date</th>
                  <th className="px-6 py-3">Reference</th>
                  <th className="px-6 py-3 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {payments.data.results.map((payment) => (
                  <tr key={payment.id} className="border-b border-gray-200 last:border-0 dark:border-gray-700">
                    <td className="px-6 py-4">{formatDate(payment.payment_date)}</td>
                    <td className="px-6 py-4 font-mono text-xs text-gray-400">{payment.payment_reference || '—'}</td>
                    <td className="px-6 py-4 text-right font-medium text-green-600 dark:text-green-400">+{formatMoney(Number(payment.amount))}</td>
                  </tr>
                ))}
                {payments.data.results.length === 0 && (
                  <tr>
                    <td colSpan={3} className="px-6 py-8 text-center text-gray-400">
                      No payments recorded
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            {payments.data.count > payments.data.results.length && (
              <p className="px-6 py-3 text-xs text-gray-500 dark:text-gray-400">
                Showing the latest {payments.data.results.length} of {payments.data.count} payments.
              </p>
            )}
          </>
        )}
      </section>
    </div>
  )
}
