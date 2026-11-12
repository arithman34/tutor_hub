import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate } from 'react-router'

import { applyServerErrors } from '../../components/formHelpers'
import { ErrorMessage, PageHeader, buttonPrimary, buttonSecondary } from '../../components/ui'
import { StudentFields } from './StudentFields'
import { useCreateStudent } from './queries'
import { emptyStudentForm, studentFormFields, studentFormSchema, toRequest, type StudentFormValues } from './studentForm'

export function NewStudentPage() {
  const navigate = useNavigate()
  const create = useCreateStudent()
  const [formError, setFormError] = useState<string | null>(null)
  // zodResolver runs the schema on submit; field errors land in formState.errors.
  const form = useForm<StudentFormValues>({ resolver: zodResolver(studentFormSchema), defaultValues: emptyStudentForm })

  const onSubmit = form.handleSubmit((values) => {
    setFormError(null)
    create.mutate(toRequest(values), {
      onSuccess: (student) => navigate(`/students/${student.id}`),
      onError: (error) => setFormError(applyServerErrors(error, form.setError, studentFormFields)),
    })
  })

  return (
    <div>
      <PageHeader title="Add student" backTo="/students" />
      <form onSubmit={onSubmit} noValidate className="card max-w-lg space-y-4 p-6">
        {formError && <ErrorMessage>{formError}</ErrorMessage>}
        <StudentFields form={form} />
        <div className="flex gap-3 pt-2">
          <button type="submit" disabled={create.isPending} className={buttonPrimary}>
            {create.isPending ? 'Adding…' : 'Add student'}
          </button>
          <Link to="/students" className={buttonSecondary}>
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
