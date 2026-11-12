import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { useMe } from '../../auth'
import { Field } from '../../components/form'
import { applyServerErrors, describedBy } from '../../components/formHelpers'
import { Tabs } from '../../components/Tabs'
import { ErrorMessage, Loading, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { useCalendarStatus } from '../connections/queries'
import { useStudents } from '../students/queries'
import { useBookLessons } from './queries'
import { WEEKDAYS, emptyScheduleForm, scheduleFormSchema, type ScheduleFormValues } from './scheduleForm'

const KINDS = [
  { value: 'oneoff', label: 'One-off' },
  { value: 'recurring', label: 'Weekly' },
] as const

const SERVER_FIELDS = ['student_id', 'date', 'start_time', 'end_time', 'start_date', 'end_date', 'interval_weeks'] as const

/** What to tell the Sessions page once Google has the booking. */
function bookedNotice({ requested, created }: { requested: number; created: number }) {
  if (requested === 1) return 'Added to Google Calendar.'
  if (created === requested) return `Added ${created} weekly lessons to Google Calendar.`
  return `Added ${created} of ${requested} weekly lessons. Google Calendar refused the rest, so check your calendar.`
}

export function ScheduleSessionPage() {
  const navigate = useNavigate()
  const me = useMe()
  const status = useCalendarStatus()
  const students = useStudents('')
  const book = useBookLessons()
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm<ScheduleFormValues>({ resolver: zodResolver(scheduleFormSchema), defaultValues: emptyScheduleForm })
  const { register, control, setValue, formState } = form
  const errors = formState.errors
  const [kind, studentId, repeatsForever, days] = useWatch({ control, name: ['kind', 'student_id', 'repeats_forever', 'days'] })

  if (status.isPending || students.isPending) return <Loading>Loading…</Loading>
  if (status.isError) return <ErrorMessage>Couldn't check your Google connection: {status.error.message}</ErrorMessage>
  if (students.isError) return <ErrorMessage>Couldn't load your students: {students.error.message}</ErrorMessage>

  if (!status.data.connected) {
    return (
      <div>
        <PageHeader title="Schedule session" backTo="/sessions" />
        <ErrorMessage>
          Connect Google Calendar before scheduling sessions.{' '}
          <Link to="/connections" className="font-medium underline">
            Go to Connections
          </Link>
        </ErrorMessage>
      </div>
    )
  }

  const activeStudents = students.data.filter((student) => student.is_active)
  const chosen = activeStudents.find((student) => student.id === studentId)
  const address = me.data?.address

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    book.mutate(values, {
      onSuccess: (result) => {
        if (result.created === 0) {
          setFormError("Google Calendar didn't accept the booking. Try again, or reconnect Google on the Connections page.")
          return
        }
        navigate('/sessions', { state: { notice: bookedNotice(result) } })
      },
      onError: (error) => setFormError(applyServerErrors(error, form.setError, SERVER_FIELDS)),
    })
  })

  return (
    <div>
      <PageHeader title="Schedule session" backTo="/sessions" />
      <form onSubmit={onSubmit} noValidate className="card max-w-2xl space-y-5 p-6">
        {formError && <ErrorMessage>{formError}</ErrorMessage>}

        <div>
          <span className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Session type</span>
          <Tabs label="Session type" options={KINDS} value={kind} onChange={(value) => setValue('kind', value)} />
        </div>

        <Field
          id="student_id"
          label="Student"
          error={errors.student_id?.message}
          hint={
            <>
              Google Calendar title: <span className="font-medium">{chosen ? `${chosen.first_name} - Tuition` : 'choose a student'}</span>
              {' · '}
              {address ? `Location: ${address}` : 'No location. Add a tutoring address on your profile to include one.'}
            </>
          }
        >
          <select {...register('student_id')} {...describedBy('student_id', errors.student_id?.message)} className="input">
            <option value="">Choose a student…</option>
            {activeStudents.map((student) => (
              <option key={student.id} value={student.id}>
                {student.first_name} {student.last_name}
              </option>
            ))}
          </select>
        </Field>

        {kind === 'oneoff' ? (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field id="date" label="Date" error={errors.date?.message}>
              <input type="date" {...register('date')} {...describedBy('date', errors.date?.message)} className="input" />
            </Field>
            <Field id="start_time" label="Start time" error={errors.start_time?.message}>
              <input type="time" {...register('start_time')} {...describedBy('start_time', errors.start_time?.message)} className="input" />
            </Field>
            <Field id="end_time" label="End time" error={errors.end_time?.message}>
              <input type="time" {...register('end_time')} {...describedBy('end_time', errors.end_time?.message)} className="input" />
            </Field>
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-3">
              <Field id="start_date" label="Starting from" error={errors.start_date?.message}>
                <input type="date" {...register('start_date')} {...describedBy('start_date', errors.start_date?.message)} className="input" />
              </Field>
              <Field id="end_date" label="Until" error={errors.end_date?.message}>
                <input
                  type="date"
                  disabled={repeatsForever}
                  {...register('end_date')}
                  {...describedBy('end_date', errors.end_date?.message)}
                  className="input disabled:opacity-50"
                />
              </Field>
              <Field id="interval_weeks" label="Every … weeks" error={errors.interval_weeks?.message}>
                <input
                  type="number"
                  min={1}
                  max={52}
                  {...register('interval_weeks', { valueAsNumber: true })}
                  {...describedBy('interval_weeks', errors.interval_weeks?.message)}
                  className="input"
                />
              </Field>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
              <input type="checkbox" {...register('repeats_forever')} className="rounded" />
              No end date (repeats until you delete it)
            </label>

            <fieldset aria-describedby={errors.days?.root ? 'days-error' : undefined}>
              <legend className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">Days and times</legend>
              <div className="space-y-2">
                {WEEKDAYS.map((weekday, index) => {
                  const enabled = days[index]?.enabled ?? false
                  const error = errors.days?.[index]?.end?.message
                  return (
                    <div key={weekday}>
                      <div className="flex flex-wrap items-center gap-3">
                        <label className="flex w-32 items-center gap-2 text-sm">
                          <input type="checkbox" {...register(`days.${index}.enabled`)} className="rounded" />
                          {weekday}
                        </label>
                        <input
                          type="time"
                          aria-label={`${weekday} start`}
                          disabled={!enabled}
                          {...register(`days.${index}.start`)}
                          className="input !w-32 disabled:opacity-50"
                        />
                        <span aria-hidden="true" className="text-gray-400">
                          –
                        </span>
                        <input
                          type="time"
                          aria-label={`${weekday} end`}
                          disabled={!enabled}
                          {...register(`days.${index}.end`)}
                          {...(error && { 'aria-invalid': true, 'aria-describedby': `day-${index}-error` })}
                          className="input !w-32 disabled:opacity-50"
                        />
                      </div>
                      {error && (
                        <p id={`day-${index}-error`} className="mt-1 text-xs text-red-600 dark:text-red-400">
                          {weekday}: {error}
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
              {errors.days?.root && (
                <p id="days-error" className="mt-2 text-xs text-red-600 dark:text-red-400">
                  {errors.days.root.message}
                </p>
              )}
            </fieldset>
          </>
        )}

        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={book.isPending} className={buttonPrimary}>
            {book.isPending ? 'Adding…' : 'Add to Google Calendar'}
          </button>
          <Link to="/sessions" className={buttonSecondary}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
