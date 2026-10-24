type SkeletonProps = { className?: string }

export function Skeleton({ className = '' }: SkeletonProps) {
  return <span aria-hidden="true" className={`skeleton ${className}`} />
}

export function PageSkeleton({ cards = 3 }: { cards?: number }) {
  return <section className="page page--loading" aria-busy="true">
    <span className="sr-only">Loading</span>
    <Skeleton className="skeleton--eyebrow" />
    <Skeleton className="skeleton--title" />
    <Skeleton className="skeleton--subtitle" />
    <div className="card-grid">
      {Array.from({ length: cards }, (_, index) => <article className="card" key={index}><Skeleton className="skeleton--label" /><Skeleton className="skeleton--line" /><Skeleton className="skeleton--line skeleton--line-short" /></article>)}
    </div>
  </section>
}
