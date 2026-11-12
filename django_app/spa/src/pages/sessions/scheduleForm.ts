import { z } from 'zod'

import type { components } from '../../api/schema'

export type OneOffBooking = components['schemas']['OneOffEventRequest']
export type RecurringBooking = components['schemas']['RecurringEventsRequest']

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] as const

const daySchema = z.object({ enabled: z.boolean(), start: z.string(), end: z.string() })

/**
 * One form for both kinds of booking. Only the fields for the chosen kind are
 * checked, so switching between them doesn't leave errors on hidden fields.
 * Times are "HH:MM" strings, so comparing them as text compares the times.
 */
export const scheduleFormSchema = z
  .object({
    kind: z.enum(['oneoff', 'recurring']),
    student_id: z.string().min(1, 'Choose a student'),
    date: z.string(),
    start_time: z.string(),
    end_time: z.string(),
    start_date: z.string(),
    end_date: z.string(),
    repeats_forever: z.boolean(),
    interval_weeks: z.number(),
    days: z.array(daySchema).length(7),
  })
  .superRefine((values, ctx) => {
    const issue = (path: (string | number)[], message: string) => ctx.addIssue({ code: 'custom', path, message })

    if (values.kind === 'oneoff') {
      if (!values.date) issue(['date'], 'Choose a date')
      if (!values.start_time) issue(['start_time'], 'Choose a start time')
      if (!values.end_time) issue(['end_time'], 'Choose an end time')
      else if (values.end_time <= values.start_time) issue(['end_time'], 'Must be after the start time')
      return
    }

    if (!values.start_date) issue(['start_date'], 'Choose the first week')
    if (!values.repeats_forever) {
      if (!values.end_date) issue(['end_date'], 'Choose an end date, or tick "No end date"')
      else if (values.start_date && values.end_date < values.start_date) issue(['end_date'], 'Must be on or after the start date')
    }
    if (!Number.isInteger(values.interval_weeks) || values.interval_weeks < 1 || values.interval_weeks > 52) {
      issue(['interval_weeks'], 'Enter a whole number of weeks from 1 to 52')
    }
    if (!values.days.some((day) => day.enabled)) issue(['days', 'root'], 'Choose at least one day')
    values.days.forEach((day, index) => {
      if (day.enabled && (!day.start || !day.end || day.end <= day.start)) issue(['days', index, 'end'], 'Must end after it starts')
    })
  })

export type ScheduleFormValues = z.infer<typeof scheduleFormSchema>

export const emptyScheduleForm: ScheduleFormValues = {
  kind: 'oneoff',
  student_id: '',
  date: '',
  start_time: '09:00',
  end_time: '10:00',
  start_date: '',
  end_date: '',
  repeats_forever: false,
  interval_weeks: 1,
  days: WEEKDAYS.map(() => ({ enabled: false, start: '09:00', end: '10:00' })),
}

/** The server titles the event after the student and adds your tutoring address. */
export function toOneOffBooking(values: ScheduleFormValues): OneOffBooking {
  return { student_id: values.student_id, date: values.date, start_time: values.start_time, end_time: values.end_time }
}

export function toRecurringBooking(values: ScheduleFormValues): RecurringBooking {
  return {
    student_id: values.student_id,
    start_date: values.start_date,
    end_date: values.repeats_forever ? null : values.end_date,
    interval_weeks: values.interval_weeks,
    day_configs: values.days.flatMap((day, weekday) => (day.enabled ? [{ weekday, start: day.start, end: day.end }] : [])),
  }
}
