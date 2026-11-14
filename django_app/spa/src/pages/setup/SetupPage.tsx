import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router'
import { z } from 'zod'

import { useLogin } from '../../auth'
import { AuthLayout } from '../../components/AuthLayout'
import { Field } from '../../components/form'
import { applyServerErrors, describedBy } from '../../components/formHelpers'
import { ErrorMessage, Loading, buttonPrimary } from '../../components/ui'
import { useCreateFirstAccount, useSetupStatus } from './queries'

const setupSchema = z
  .object({
    first_name: z.string().trim().min(1, 'Enter your first name').max(150, 'At most 150 characters'),
    last_name: z.string().trim().min(1, 'Enter your last name').max(150, 'At most 150 characters'),
    email: z.string().trim().pipe(z.email('Enter a valid email address')),
    password: z.string().min(1, 'Choose a password'),
    confirm_password: z.string(),
  })
  .refine((values) => values.password === values.confirm_password, { path: ['confirm_password'], message: "Passwords don't match" })
type SetupValues = z.infer<typeof setupSchema>
const SERVER_FIELDS = ['first_name', 'last_name', 'email', 'password'] as const

/** First run: create the only account. Shown only while no account exists. */
export function SetupPage() {
  const status = useSetupStatus()
  const create = useCreateFirstAccount()
  const login = useLogin()
  const navigate = useNavigate()
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<SetupValues>({
    resolver: zodResolver(setupSchema),
    defaultValues: { first_name: '', last_name: '', email: '', password: '', confirm_password: '' },
  })
  const { register, formState } = form
  const errors = formState.errors

  if (status.isPending) return <Loading>Loading…</Loading>
  if (status.isError) return <ErrorMessage>Couldn't reach TutorHub: {status.error.message}</ErrorMessage>
  // Once an account exists (including the one just made here) setup is over.
  if (!status.data.needed && !create.isSuccess) return <Navigate to="/login" replace />

  const onSubmit = form.handleSubmit(({ first_name, last_name, email, password }) => {
    setFormError(null)
    const values = { first_name, last_name, email, password }
    create.mutate(values, {
      // Sign straight in with the new account rather than asking again.
      onSuccess: () =>
        login.mutate(
          { email: values.email, password: values.password },
          { onSuccess: () => navigate('/', { replace: true }), onError: () => navigate('/login', { replace: true }) },
        ),
      onError: (error) => setFormError(applyServerErrors(error, form.setError, SERVER_FIELDS)),
    })
  })

  const busy = create.isPending || login.isPending

  return (
    <AuthLayout title="Welcome to TutorHub" description="Create your account to get started.">

        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {formError && <ErrorMessage>{formError}</ErrorMessage>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field id="first_name" label="First name" error={errors.first_name?.message}>
              <input autoComplete="given-name" {...register('first_name')} {...describedBy('first_name', errors.first_name?.message)} className="input" />
            </Field>
            <Field id="last_name" label="Last name" error={errors.last_name?.message}>
              <input autoComplete="family-name" {...register('last_name')} {...describedBy('last_name', errors.last_name?.message)} className="input" />
            </Field>
          </div>
          <Field id="email" label="Email" error={errors.email?.message}>
            <input type="email" autoComplete="email" {...register('email')} {...describedBy('email', errors.email?.message)} className="input" />
          </Field>
          <Field id="password" label="Password" error={errors.password?.message}>
            <input type="password" autoComplete="new-password" {...register('password')} {...describedBy('password', errors.password?.message)} className="input" />
          </Field>
          <Field id="confirm_password" label="Confirm password" error={errors.confirm_password?.message}>
            <input
              type="password"
              autoComplete="new-password"
              {...register('confirm_password')}
              {...describedBy('confirm_password', errors.confirm_password?.message)}
              className="input"
            />
          </Field>
          <button type="submit" disabled={busy} className={`${buttonPrimary} w-full`}>
            {busy ? 'Creating your account…' : 'Create account'}
          </button>
        </form>
    </AuthLayout>
  )
}
