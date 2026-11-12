import type { UseFormReturn } from 'react-hook-form'

import { Field } from '../../components/form'
import { describedBy } from '../../components/formHelpers'
import type { PayeeFormValues } from './payeeForm'

export function PayeeFields({ form }: { form: UseFormReturn<PayeeFormValues> }) {
  const { register, formState } = form
  const errors = formState.errors

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="first_name" label="First name" error={errors.first_name?.message}>
          <input {...register('first_name')} {...describedBy('first_name', errors.first_name?.message)} className="input" />
        </Field>
        <Field id="last_name" label="Last name" error={errors.last_name?.message}>
          <input {...register('last_name')} {...describedBy('last_name', errors.last_name?.message)} className="input" />
        </Field>
      </div>
      <Field id="email" label="Email (optional)" error={errors.email?.message}>
        <input type="email" {...register('email')} {...describedBy('email', errors.email?.message)} className="input" />
      </Field>
      <Field id="phone_number" label="Phone number (optional)" error={errors.phone_number?.message}>
        <input type="tel" {...register('phone_number')} {...describedBy('phone_number', errors.phone_number?.message)} className="input" />
      </Field>
      <Field
        id="bank_reference_pattern"
        label="Bank reference (optional)"
        error={errors.bank_reference_pattern?.message}
        hint="The reference this payee uses on bank transfers, e.g. SMITH-JAN."
      >
        <input
          {...register('bank_reference_pattern')}
          {...describedBy('bank_reference_pattern', errors.bank_reference_pattern?.message)}
          className="input font-mono"
        />
      </Field>
    </>
  )
}
