import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { ApiError } from '../api/client'
import { useLogin, useMe } from '../auth'
import { AuthLayout } from '../components/AuthLayout'
import { useSetupStatus } from './setup/queries'

export function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const me = useMe()
  const login = useLogin()
  const setup = useSetupStatus()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (me.data) return <Navigate to={from} replace />
  // A brand-new TutorHub has no account to sign in to yet.
  if (setup.data?.needed) return <Navigate to="/setup" replace />

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    login.mutate({ email, password }, { onSuccess: () => navigate(from, { replace: true }) })
  }

  const error =
    login.error instanceof ApiError && login.error.status === 401
      ? 'Invalid email or password'
      : login.error
        ? "Couldn't sign in. Try again in a moment."
        : null

  return (
    <AuthLayout title="Sign in" description="Welcome back. Sign in to your TutorHub account.">
      {error && (
        <p role="alert" className="alert alert-error mb-4">
          {error}
        </p>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="field-label">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="input"
          />
        </div>
        <div>
          <label htmlFor="password" className="field-label">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="input"
          />
        </div>
        <button type="submit" disabled={login.isPending} className="btn btn-primary w-full">
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  )
}
