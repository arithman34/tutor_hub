import type { UseFormReturn } from 'react-hook-form'

import { Field } from '../../components/form'
import { describedBy } from '../../components/formHelpers'
import { googleDocUrl, type StudentFormValues } from './studentForm'
import { usePayees } from '../payees/queries'

/** The inputs shared by the add and edit forms. */
export function StudentFields({ form, savedDocId }: { form: UseFormReturn<StudentFormValues>; savedDocId?: string | null }) {
  const payees = usePayees()
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
      <Field id="level" label="Level" error={errors.level?.message}>
        <input
          {...register('level')}
          {...describedBy('level', errors.level?.message)}
          placeholder="e.g. GCSE, A-Level, KS3"
          className="input"
        />
      </Field>
      <Field id="hourly_rate" label="Hourly rate (£)" error={errors.hourly_rate?.message}>
        <input
          {...register('hourly_rate')}
          {...describedBy('hourly_rate', errors.hourly_rate?.message)}
          inputMode="decimal"
          className="input"
        />
      </Field>
      <Field id="payee_id" label="Payee (optional)" error={errors.payee_id?.message}>
        <select {...register('payee_id')} {...describedBy('payee_id', errors.payee_id?.message)} className="input">
          <option value="">— No payee —</option>
          {payees.data?.map((payee) => (
            <option key={payee.id} value={payee.id}>
              {payee.first_name} {payee.last_name}
            </option>
          ))}
        </select>
      </Field>
      {savedDocId !== undefined && (
        <Field
          id="ilp_url"
          label="ILP document URL"
          error={errors.ilp_url?.message}
          hint={
            savedDocId && (
              <a href={googleDocUrl(savedDocId)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline dark:text-blue-400">
                Open ILP
              </a>
            )
          }
        >
          <input
            {...register('ilp_url')}
            {...describedBy('ilp_url', errors.ilp_url?.message)}
            type="url"
            placeholder="https://docs.google.com/document/d/..."
            className="input"
          />
        </Field>
      )}
    </>
  )
}
