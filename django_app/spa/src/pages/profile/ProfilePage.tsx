import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { api, unwrap } from '../../api/client'
import type { User } from '../../api/types'
import { meQueryKey, useMe } from '../../auth'
import { Field } from '../../components/form'
import { applyServerErrors, describedBy } from '../../components/formHelpers'
import { ErrorMessage, Loading, PageHeader, buttonPrimary } from '../../components/ui'

const detailsSchema = z.object({
  first_name: z.string().trim().min(1, 'Enter your first name').max(150, 'At most 150 characters'),
  last_name: z.string().trim().min(1, 'Enter your last name').max(150, 'At most 150 characters'),
  email: z.string().trim().pipe(z.email('Enter a valid email address')),
  address: z.string().trim().max(255, 'At most 255 characters'),
})
type DetailsValues = z.infer<typeof detailsSchema>
const DETAILS_FIELDS = ['first_name', 'last_name', 'email', 'address'] as const

const passwordSchema = z
  .object({
    current_password: z.string().min(1, 'Enter your current password'),
    new_password: z.string().min(1, 'Enter a new password'),
    confirm_password: z.string(),
  })
  .refine((values) => values.new_password === values.confirm_password, { path: ['confirm_password'], message: "Passwords don't match" })
type PasswordValues = z.infer<typeof passwordSchema>
const PASSWORD_FIELDS = ['current_password', 'new_password'] as const

function Saved({ children }: { children: string }) {
  return (
    <p role="status" className="text-sm text-green-600 dark:text-green-400">
      {children}
    </p>
  )
}

function DetailsForm({ user }: { user: User }) {
  const queryClient = useQueryClient()
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<DetailsValues>({
    resolver: zodResolver(detailsSchema),
    defaultValues: { first_name: user.first_name, last_name: user.last_name, email: user.email, address: user.address ?? '' },
  })
  const { register, formState } = form
  const errors = formState.errors

  const save = useMutation({
    mutationFn: async (values: DetailsValues) =>
      unwrap(await api.PATCH('/api/v1/auth/me', { body: { ...values, address: values.address || null } })),
    onSuccess: (saved) => {
      // The sidebar shows your name from this same cache entry.
      queryClient.setQueryData(meQueryKey, saved)
      form.reset({ first_name: saved.first_name, last_name: saved.last_name, email: saved.email, address: saved.address ?? '' })
    },
  })

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    save.mutate(values, { onError: (error) => setFormError(applyServerErrors(error, form.setError, DETAILS_FIELDS)) })
  })

  return (
    <section aria-labelledby="details-heading" className="card p-6">
      <h2 id="details-heading" className="font-semibold">
        Personal info
      </h2>
      <p className="mt-1 mb-5 text-sm text-gray-500 dark:text-gray-400">Your name, sign-in email and tutoring address.</p>
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
        <Field id="address" label="Tutoring address (optional)" error={errors.address?.message} hint="Used as the location on lessons you schedule.">
          <input autoComplete="street-address" {...register('address')} {...describedBy('address', errors.address?.message)} className="input" />
        </Field>
        <div className="flex items-center gap-4">
          <button type="submit" disabled={save.isPending} className={buttonPrimary}>
            {save.isPending ? 'Saving…' : 'Save changes'}
          </button>
          {save.isSuccess && !formState.isDirty && <Saved>Profile updated.</Saved>}
        </div>
      </form>
    </section>
  )
}

function PasswordForm() {
  const [formError, setFormError] = useState<string | null>(null)
  const form = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current_password: '', new_password: '', confirm_password: '' },
  })
  const { register, formState } = form
  const errors = formState.errors

  const change = useMutation({
    mutationFn: async ({ current_password, new_password }: PasswordValues) =>
      unwrap(await api.POST('/api/v1/auth/password', { body: { current_password, new_password } })),
    onSuccess: () => form.reset(),
  })

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    change.mutate(values, { onError: (error) => setFormError(applyServerErrors(error, form.setError, PASSWORD_FIELDS)) })
  })

  return (
    <section aria-labelledby="password-heading" className="card p-6">
      <h2 id="password-heading" className="font-semibold">
        Change password
      </h2>
      <p className="mt-1 mb-5 text-sm text-gray-500 dark:text-gray-400">
        Choose a strong password you don't use elsewhere. Changing it signs you out on every other device.
      </p>
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError && <ErrorMessage>{formError}</ErrorMessage>}
        <Field id="current_password" label="Current password" error={errors.current_password?.message}>
          <input
            type="password"
            autoComplete="current-password"
            {...register('current_password')}
            {...describedBy('current_password', errors.current_password?.message)}
            className="input"
          />
        </Field>
        <Field id="new_password" label="New password" error={errors.new_password?.message}>
          <input
            type="password"
            autoComplete="new-password"
            {...register('new_password')}
            {...describedBy('new_password', errors.new_password?.message)}
            className="input"
          />
        </Field>
        <Field id="confirm_password" label="Confirm new password" error={errors.confirm_password?.message}>
          <input
            type="password"
            autoComplete="new-password"
            {...register('confirm_password')}
            {...describedBy('confirm_password', errors.confirm_password?.message)}
            className="input"
          />
        </Field>
        <div className="flex items-center gap-4">
          <button type="submit" disabled={change.isPending} className={buttonPrimary}>
            {change.isPending ? 'Changing…' : 'Change password'}
          </button>
          {change.isSuccess && !formState.isDirty && <Saved>Password changed.</Saved>}
        </div>
      </form>
    </section>
  )
}

export function ProfilePage() {
  const me = useMe()

  return (
    <div className="max-w-2xl space-y-5">
      <PageHeader title="My profile" />
      {/* RequireAuth has already loaded you, so this is only ever briefly empty. */}
      {me.data ? <DetailsForm user={me.data} /> : <Loading />}
      <PasswordForm />
    </div>
  )
}
