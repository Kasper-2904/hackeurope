import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthFormCard } from '@/components/auth/AuthFormCard'
import { AuthInput } from '@/components/auth/AuthInput'
import { useAuth } from '@/context/AuthContext'

interface LoginFormState {
  username: string
  password: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [form, setForm] = useState<LoginFormState>({ username: '', password: '' })
  const [errors, setErrors] = useState<Partial<LoginFormState>>({})
  const [errorMessage, setErrorMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function validate(currentForm: LoginFormState): Partial<LoginFormState> {
    const nextErrors: Partial<LoginFormState> = {}
    if (!currentForm.username.trim()) {
      nextErrors.username = 'Username is required.'
    }
    if (!currentForm.password) {
      nextErrors.password = 'Password is required.'
    }
    return nextErrors
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage('')

    const nextErrors = validate(form)
    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setIsSubmitting(true)
    try {
      await login(form)
      navigate('/dashboard', { replace: true })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Login failed.'
      setErrorMessage(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <AuthFormCard
        title="Welcome back"
        subtitle="Login to access your project workspace."
        error={errorMessage}
      >
        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <AuthInput
            id="username"
            name="username"
            label="Username"
            autoComplete="username"
            value={form.username}
            error={errors.username}
            disabled={isSubmitting}
            onChange={(value) => setForm((prev) => ({ ...prev, username: value }))}
          />
          <AuthInput
            id="password"
            name="password"
            label="Password"
            type="password"
            autoComplete="current-password"
            value={form.password}
            error={errors.password}
            disabled={isSubmitting}
            onChange={(value) => setForm((prev) => ({ ...prev, password: value }))}
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-sky-300"
          >
            {isSubmitting ? 'Logging in...' : 'Login'}
          </button>
          <p className="text-center text-sm text-slate-600">
            Don&apos;t have an account?{' '}
            <Link to="/register" className="font-medium text-sky-700 hover:text-sky-800">
              Register
            </Link>
          </p>
        </form>
      </AuthFormCard>
    </div>
  )
}
