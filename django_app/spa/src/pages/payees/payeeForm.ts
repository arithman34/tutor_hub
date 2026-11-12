import { z } from 'zod'

import type { Payee, PayeeRequest } from '../../api/types'

export const payeeFormSchema = z.object({
  first_name: z.string().trim().min(1, 'Enter a first name').max(150, 'At most 150 characters'),
  last_name: z.string().trim().min(1, 'Enter a last name').max(150, 'At most 150 characters'),
  email: z
    .string()
    .trim()
    .refine((value) => value === '' || z.email().safeParse(value).success, { message: 'Enter a valid email address' }),
  phone_number: z.string().trim().max(50, 'At most 50 characters'),
  bank_reference_pattern: z.string().trim().max(255, 'At most 255 characters'),
})

export type PayeeFormValues = z.infer<typeof payeeFormSchema>

export const payeeFormFields = ['first_name', 'last_name', 'email', 'phone_number', 'bank_reference_pattern'] as const

export const emptyPayeeForm: PayeeFormValues = { first_name: '', last_name: '', email: '', phone_number: '', bank_reference_pattern: '' }

export function fromPayee(payee: Payee): PayeeFormValues {
  return {
    first_name: payee.first_name,
    last_name: payee.last_name,
    email: payee.email ?? '',
    phone_number: payee.phone_number ?? '',
    bank_reference_pattern: payee.bank_reference_pattern ?? '',
  }
}

export function toPayeeRequest(values: PayeeFormValues): PayeeRequest {
  const parsed = payeeFormSchema.parse(values)
  return {
    first_name: parsed.first_name,
    last_name: parsed.last_name,
    email: parsed.email || null,
    phone_number: parsed.phone_number || null,
    bank_reference_pattern: parsed.bank_reference_pattern || null,
  }
}
