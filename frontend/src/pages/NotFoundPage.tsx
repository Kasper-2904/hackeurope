import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="mx-auto max-w-md rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
      <h2 className="text-xl font-semibold text-slate-900">Page not found</h2>
      <p className="mt-2 text-sm text-slate-600">The page you requested does not exist.</p>
      <Link to="/" className="mt-4 inline-block rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700">
        Go to home
      </Link>
    </section>
  )
}
