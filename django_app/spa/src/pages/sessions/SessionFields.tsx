import type { UseFormReturn } from 'react-hook-form'

import type { Student } from '../../api/types'
import { Field } from '../../components/form'
import { describedBy } from '../../components/formHelpers'
import { NOTE_LABELS, notesFields, type DetailsValues, type NotesValues } from './sessionForm'

/** Student, date, start/end time and the no-show switch. */
export function DetailsFields({
  form,
  students,
  compact = false,
}: {
  form: UseFormReturn<DetailsValues>
  students: Student[]
  compact?: boolean
}) {
  const { register, formState } = form
  const errors = formState.errors
  // Inactive students are still listed (an old session may belong to one), after the active ones.
  const sorted = [...students].sort((a, b) => Number(b.is_active) - Number(a.is_active) || a.first_name.localeCompare(b.first_name))

  return (
    <>
      <Field id="student" label="Student" error={errors.student?.message}>
        <select {...register('student')} {...describedBy('student', errors.student?.message)} className="input">
          <option value="">— Select student —</option>
          {sorted.map((student) => (
            <option key={student.id} value={student.id}>
              {student.first_name} {student.last_name}
              {student.is_active ? '' : ' (inactive)'}
            </option>
          ))}
        </select>
      </Field>
      <div className={`grid gap-4 ${compact ? 'grid-cols-2' : 'sm:grid-cols-3'}`}>
        <div className={compact ? 'col-span-2' : ''}>
          <Field id="date" label="Date" error={errors.date?.message}>
            <input type="date" {...register('date')} {...describedBy('date', errors.date?.message)} className="input" />
          </Field>
        </div>
        <Field id="start_time" label="Start time" error={errors.start_time?.message}>
          <input type="time" {...register('start_time')} {...describedBy('start_time', errors.start_time?.message)} className="input" />
        </Field>
        <Field id="end_time" label="End time" error={errors.end_time?.message}>
          <input type="time" {...register('end_time')} {...describedBy('end_time', errors.end_time?.message)} className="input" />
        </Field>
      </div>
      <label className="flex cursor-pointer items-center gap-3 text-sm font-medium text-gray-700 dark:text-gray-300">
        <input type="checkbox" {...register('is_no_show')} className="h-4 w-4 rounded-sm border-gray-300 text-red-600 focus:ring-red-500" />
        Student did not show up
      </label>
    </>
  )
}

/** The five note fields. */
export function NotesFields({ form }: { form: UseFormReturn<NotesValues> }) {
  const { register, formState } = form
  return (
    <>
      {notesFields.map((name) => {
        const error = formState.errors[name]?.message
        return (
          <Field key={name} id={name} label={NOTE_LABELS[name]} error={error}>
            {name === 'topic_tags' ? (
              <input {...register(name)} {...describedBy(name, error)} placeholder="e.g. algebra, equations, revision" className="input" />
            ) : (
              <textarea {...register(name)} {...describedBy(name, error)} rows={name === 'work_covered' ? 3 : 2} className="input" />
            )}
          </Field>
        )
      })}
    </>
  )
}
