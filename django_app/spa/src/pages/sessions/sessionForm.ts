/**
 * The session forms' rules and conversions. Times are wall-clock times (see
 * format.ts): the date and HH:MM the user picks are sent as that time "in UTC",
 * exactly as the classic pages stored them.
 */
import { z } from 'zod'

import type { Session } from '../../api/types'
import { toWallIso, wallDate, wallTime } from '../../format'

const TIME = /^([01]\d|2[0-3]):[0-5]\d$/

export const detailsSchema = z
  .object({
    student: z.string().min(1, 'Choose a student'),
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Choose a date'),
    start_time: z.string().regex(TIME, 'Choose a start time'),
    end_time: z.string().regex(TIME, 'Choose an end time'),
    is_no_show: z.boolean(),
  })
  // HH:MM strings sort the same way as the times they represent.
  .refine((values) => !TIME.test(values.start_time) || !TIME.test(values.end_time) || values.end_time > values.start_time, {
    message: 'Must be after the start time',
    path: ['end_time'],
  })

export const notesSchema = z.object({
  work_covered: z.string(),
  student_actions: z.string(),
  tutor_actions: z.string(),
  next_lesson_focus: z.string(),
  topic_tags: z.string().max(255, 'At most 255 characters'),
})

export type DetailsValues = z.infer<typeof detailsSchema>
export type NotesValues = z.infer<typeof notesSchema>

export const detailsFields = ['student', 'date', 'start_time', 'end_time', 'is_no_show'] as const
export const notesFields = ['work_covered', 'student_actions', 'tutor_actions', 'next_lesson_focus', 'topic_tags'] as const

export const NOTE_LABELS: Record<keyof NotesValues, string> = {
  work_covered: 'Work covered',
  student_actions: 'Student actions',
  tutor_actions: 'Tutor actions',
  next_lesson_focus: 'Next lesson focus',
  topic_tags: 'Topic tags',
}

export const emptyNotes: NotesValues = {
  work_covered: '',
  student_actions: '',
  tutor_actions: '',
  next_lesson_focus: '',
  topic_tags: '',
}

export function detailsFromSession(session: Session): DetailsValues {
  return {
    student: session.student,
    date: wallDate(session.session_start_time),
    start_time: wallTime(session.session_start_time),
    end_time: wallTime(session.session_end_time),
    is_no_show: session.is_no_show ?? false,
  }
}

export function notesFromSession(session: Session): NotesValues {
  return {
    work_covered: session.work_covered ?? '',
    student_actions: session.student_actions ?? '',
    tutor_actions: session.tutor_actions ?? '',
    next_lesson_focus: session.next_lesson_focus ?? '',
    topic_tags: session.topic_tags ?? '',
  }
}

export function detailsToRequest(values: DetailsValues) {
  const start = toWallIso(values.date, values.start_time)
  return {
    student: values.student,
    session_date: start,
    session_start_time: start,
    session_end_time: toWallIso(values.date, values.end_time),
    is_no_show: values.is_no_show,
  }
}

/** Blank notes are stored as null, as the classic pages did. */
export function notesToRequest(values: NotesValues) {
  return {
    work_covered: values.work_covered.trim() || null,
    student_actions: values.student_actions.trim() || null,
    tutor_actions: values.tutor_actions.trim() || null,
    next_lesson_focus: values.next_lesson_focus.trim() || null,
    topic_tags: values.topic_tags.trim() || null,
  }
}
