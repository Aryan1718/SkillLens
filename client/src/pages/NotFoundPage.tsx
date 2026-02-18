import { AppLink } from '../lib/router'

export function NotFoundPage() {
  return (
    <div className="page-stack">
      <section className="section-block compact">
        <h1>404</h1>
        <p>Page not found.</p>
        <AppLink to="/">Go Home</AppLink>
      </section>
    </div>
  )
}
