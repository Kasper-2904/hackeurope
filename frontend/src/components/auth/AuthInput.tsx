interface AuthInputProps {
  id: string
  name: string
  label: string
  type?: string
  autoComplete?: string
  value: string
  disabled?: boolean
  error?: string
  onChange: (value: string) => void
}

export function AuthInput({
  id,
  name,
  label,
  type = 'text',
  autoComplete,
  value,
  disabled,
  error,
  onChange,
}: AuthInputProps) {
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      <input
        id={id}
        name={name}
        type={type}
        autoComplete={autoComplete}
        value={value}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 disabled:bg-slate-100"
      />
      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </div>
  )
}
