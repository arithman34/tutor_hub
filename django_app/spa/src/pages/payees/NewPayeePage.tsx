import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { applyServerErrors } from '../../components/formHelpers'
import { ErrorMessage, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { PayeeFields } from './PayeeFields'
import { emptyPayeeForm, payeeFormFields, payeeFormSchema, toPayeeRequest, type PayeeFormValues } from './payeeForm'
import { useCreatePayee } from './queries'

export function NewPayeePage() {
  const navigate = useNavigate()
  const create = useCreatePayee()
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<PayeeFormValues>({ resolver: zodResolver(payeeFormSchema), defaultValues: emptyPayeeForm })

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    create.mutate(toPayeeRequest(values), {
      onSuccess: (payee) => navigate(`/payees/${payee.id}`),
      onError: (error) => setFormError(applyServerErrors(error, form.setError, payeeFormFields)),
    })
  })

  return (
    <div>
      <PageHeader title="Add payee" backTo="/payees" />
      <form onSubmit={onSubmit} noValidate className="card max-w-lg space-y-4 p-6">
        {formError && <ErrorMessage>{formError}</ErrorMessage>}
        <PayeeFields form={form} />
        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={create.isPending} className={buttonPrimary}>
            {create.isPending ? 'Adding…' : 'Add payee'}
          </button>
          <Link to="/payees" className={buttonSecondary}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
