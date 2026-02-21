import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AuthFormCard } from '@/components/auth/AuthFormCard'
import { AuthInput } from '@/components/auth/AuthInput'
import { useAuth } from '@/context/AuthContext'

interface RegisterFormState {
  email: string
  username: string
  password: string
  confirmPassword: string
  fullName: string
}

export function RegisterPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [form, setForm] = useState<RegisterFormState>({
    email: '',
    username: '',
    password: '',
    confirmPassword: '',
    fullName: '',
  })
  const [errors, setErrors] = useState<Partial<RegisterFormState>>({})
  const [errorMessage, setErrorMessage] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function validate(currentForm: RegisterFormState): Partial<RegisterFormState> {
    const nextErrors: Partial<RegisterFormState> = {}

    if (!currentForm.email.trim()) {
      nextErrors.email = 'Email is required.'
    }

    if (!currentForm.username.trim()) {
      nextErrors.username = 'Username is required.'
    }

    if (!currentForm.password) {
      nextErrors.password = 'Password is required.'
    } else if (currentForm.password.length < 8) {
      nextErrors.password = 'Password must be at least 8 characters.'
    }

    if (!currentForm.confirmPassword) {
      nextErrors.confirmPassword = 'Please confirm your password.'
    } else if (currentForm.password !== currentForm.confirmPassword) {
      nextErrors.confirmPassword = 'Passwords do not match.'
    }

    return nextErrors
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage('')
    setSuccessMessage('')

    const nextErrors = validate(form)
    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setIsSubmitting(true)
    try {
      await register({
        email: form.email,
        username: form.username,
        password: form.password,
        full_name: form.fullName.trim() || undefined,
      })
      setSuccessMessage('Account created. Redirecting to login...')
      setTimeout(() => {
        navigate('/login', { replace: true })
      }, 900)
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Registration failed.'
      setErrorMessage(message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-10">
      <AuthFormCard
        title="Create account"
        subtitle="Register to access project dashboards and workflows."
        error={errorMessage}
        success={successMessage}
      >
        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <AuthInput
            id="email"
            name="email"
            label="Email"
            type="email"
            autoComplete="email"
            value={form.email}
            error={errors.email}
            disabled={isSubmitting}
            onChange={(value) => setForm((prev) => ({ ...prev, email: value }))}
          />
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
            id="fullName"
            name="fullName"
            label="Full name (optional)"
            autoComplete="name"
            value={form.fullName}
            error={errors.fullName}
            disabled={isSubmitting}
            onChange={(value) => setForm((prev) => ({ ...prev, fullName: value }))}
          />
          <AuthInput
            id="password"
            name="password"
            label="Password"
            type="password"
            autoComplete="new-password"
            value={form.password}
            error={errors.password}
            disabled={isSubmitting}
            onChange={(value) => setForm((prev) => ({ ...prev, password: value }))}
          />
          <AuthInput
            id="confirmPassword"
            name="confirmPassword"
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            value={form.confirmPassword}
            error={errors.confirmPassword}
            disabled={isSubmitting}
            onChange={(value) => setForm((prev) => ({ ...prev, confirmPassword: value }))}
          />
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:bg-sky-300"
          >
            {isSubmitting ? 'Creating account...' : 'Register'}
          </button>
          <p className="text-center text-sm text-slate-600">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-sky-700 hover:text-sky-800">
              Login
            </Link>
          </p>
        </form>
      </AuthFormCard>
    </div>
  )
}
