/**
 * The student form's rules, in one Zod schema used by both the add and edit
 * pages. The form works with strings (what inputs hold); toRequest() turns
 * them into the API's shape (numbers, nulls). The server validates again,
 * so these rules are for quick feedback, not security.
 */
import { z } from 'zod'

import type { Student, StudentRequest } from '../../api/types'

const GOOGLE_DOC_URL = /\/document\/d\/([a-zA-Z0-9_-]+)/

export const studentFormSchema = z.object({
  first_name: z.string().trim().min(1, 'Enter a first name').max(150, 'At most 150 characters'),
  last_name: z.string().trim().min(1, 'Enter a last name').max(150, 'At most 150 characters'),
  level: z.string().trim().max(100, 'At most 100 characters'),
  hourly_rate: z
    .string()
    .trim()
    .refine((value) => value === '' || (/^\d+(\.\d{1,2})?$/.test(value) && Number(value) >= 0), {
      message: 'Enter an amount like 30 or 27.50',
    }),
  payee_id: z.string(),
  ilp_url: z
    .string()
    .trim()
    .refine((value) => value === '' || GOOGLE_DOC_URL.test(value), {
      message: 'Paste a Google Docs link (…/document/d/…)',
    }),
})

export type StudentFormValues = z.infer<typeof studentFormSchema>

export const studentFormFields = ['first_name', 'last_name', 'level', 'hourly_rate', 'payee_id', 'ilp_url'] as const

export const emptyStudentForm: StudentFormValues = {
  first_name: '',
  last_name: '',
  level: '',
  hourly_rate: '',
  payee_id: '',
  ilp_url: '',
}

export function googleDocUrl(docId: string): string {
  return `https://docs.google.com/document/d/${docId}/`
}

export function fromStudent(student: Student): StudentFormValues {
  return {
    first_name: student.first_name,
    last_name: student.last_name,
    level: student.level ?? '',
    hourly_rate: student.hourly_rate === null || student.hourly_rate === undefined ? '' : String(student.hourly_rate),
    payee_id: student.payee_id ?? '',
    ilp_url: student.google_doc_id ? googleDocUrl(student.google_doc_id) : '',
  }
}

export function toRequest(values: StudentFormValues): StudentRequest {
  const parsed = studentFormSchema.parse(values)
  return {
    first_name: parsed.first_name,
    last_name: parsed.last_name,
    level: parsed.level || null,
    hourly_rate: parsed.hourly_rate === '' ? null : Number(parsed.hourly_rate),
    payee_id: parsed.payee_id || null,
    google_doc_id: parsed.ilp_url.match(GOOGLE_DOC_URL)?.[1] ?? null,
  }
}
