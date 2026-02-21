interface AuthFormCardProps {
  title: string
  subtitle: string
  error?: string
  success?: string
  children: React.ReactNode
}

export function AuthFormCard({ title, subtitle, error, success, children }: AuthFormCardProps) {
  return (
    <div className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-1 text-sm text-slate-600">{subtitle}</p>
      {error ? <p className="mt-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p> : null}
      {success ? <p className="mt-4 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p> : null}
      <div className="mt-5">{children}</div>
    </div>
  )
}
