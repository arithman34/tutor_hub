import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { z } from 'zod'

import { Field } from '../../components/form'
import { applyServerErrors, describedBy } from '../../components/formHelpers'
import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { toWallIso } from '../../format'
import { useCreatePayment, usePayees } from '../payees/queries'

const paymentFormSchema = z.object({
  payee: z.string().min(1, 'Choose a payee'),
  amount: z
    .string()
    .trim()
    .refine((value) => /^\d+(\.\d{1,2})?$/.test(value) && Number(value) > 0, { message: 'Enter an amount like 40 or 37.50' }),
  payment_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Choose a date'),
  payment_reference: z.string().trim().max(255, 'At most 255 characters'),
})

type PaymentFormValues = z.infer<typeof paymentFormSchema>
const paymentFormFields = ['payee', 'amount', 'payment_date', 'payment_reference'] as const

/** Today in the UK, as YYYY-MM-DD: the date a payment usually arrives. */
function todayInUk(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/London' }).format(new Date())
}

export function NewPaymentPage() {
  const navigate = useNavigate()
  // "Add payment" on a payee's page pre-selects them (?payee_id=…).
  const [searchParams] = useSearchParams()
  const presetPayee = searchParams.get('payee_id') ?? ''
  const payees = usePayees()
  const create = useCreatePayment()
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<PaymentFormValues>({
    resolver: zodResolver(paymentFormSchema),
    defaultValues: { payee: presetPayee, amount: '', payment_date: todayInUk(), payment_reference: '' },
  })
  const errors = form.formState.errors

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    create.mutate(
      {
        payee: values.payee,
        amount: values.amount,
        // Like session times, the chosen day is stored as that date's midnight "in UTC".
        payment_date: toWallIso(values.payment_date, '00:00'),
        payment_reference: values.payment_reference || null,
      },
      {
        // Back to the payee if we came from their page, otherwise to the list.
        onSuccess: (payment) => navigate(presetPayee ? `/payees/${payment.payee}` : '/payments'),
        onError: (error) => setFormError(applyServerErrors(error, form.setError, paymentFormFields)),
      },
    )
  })

  if (payees.isPending) return <Loading>Loading payees…</Loading>
  if (payees.isError) return <ErrorMessage>Couldn't load your payees: {payees.error.message}</ErrorMessage>

  const backTo = presetPayee ? `/payees/${presetPayee}` : '/payments'

  return (
    <div>
      <PageHeader title="Add payment" backTo={backTo} />
      {payees.data.length === 0 ? (
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Payments are recorded against a payee.{' '}
          <Link to="/payees/new" className="text-blue-600 underline dark:text-blue-400">
            Add a payee
          </Link>{' '}
          first.
        </p>
      ) : (
        <form onSubmit={onSubmit} noValidate className="card max-w-lg space-y-4 p-6">
          {formError && <ErrorMessage>{formError}</ErrorMessage>}
          <Field id="payee" label="Payee" error={errors.payee?.message}>
            <select {...form.register('payee')} {...describedBy('payee', errors.payee?.message)} className="input">
              <option value="">— Select payee —</option>
              {payees.data.map((payee) => (
                <option key={payee.id} value={payee.id}>
                  {payee.first_name} {payee.last_name}
                </option>
              ))}
            </select>
          </Field>
          <Field id="amount" label="Amount (£)" error={errors.amount?.message}>
            <input {...form.register('amount')} {...describedBy('amount', errors.amount?.message)} inputMode="decimal" className="input" />
          </Field>
          <Field id="payment_date" label="Payment date" error={errors.payment_date?.message}>
            <input type="date" {...form.register('payment_date')} {...describedBy('payment_date', errors.payment_date?.message)} className="input" />
          </Field>
          <Field id="payment_reference" label="Reference (optional)" error={errors.payment_reference?.message}>
            <input
              {...form.register('payment_reference')}
              {...describedBy('payment_reference', errors.payment_reference?.message)}
              placeholder="e.g. bank transfer reference"
              className="input"
            />
          </Field>
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={create.isPending} className={buttonPrimary}>
              {create.isPending ? 'Adding…' : 'Add payment'}
            </button>
            <Link to={backTo} className={buttonSecondary}>
              Cancel
            </Link>
          </div>
        </form>
      )}
    </div>
  )
}
