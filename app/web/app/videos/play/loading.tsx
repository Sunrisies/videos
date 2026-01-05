export default function Loading() {
  return (
    <div className="min-h-screen bg-black">
      <header className="fixed top-0 left-0 right-0 z-20 bg-black/80 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="h-10 w-10 bg-white/10 animate-pulse rounded" />
          <div className="flex gap-2">
            <div className="h-10 w-10 bg-white/10 animate-pulse rounded" />
            <div className="h-10 w-10 bg-white/10 animate-pulse rounded" />
          </div>
        </div>
      </header>

      <div className="pt-12">
        <div className="relative w-full aspect-video bg-muted animate-pulse" />
      </div>

      <div className="bg-background">
        <div className="px-4 py-6 space-y-4">
          <div className="h-7 bg-muted animate-pulse rounded w-3/4" />
          <div className="h-4 bg-muted animate-pulse rounded w-1/2" />
          <div className="border-t pt-4 space-y-2">
            <div className="h-4 bg-muted animate-pulse rounded w-1/4" />
            <div className="h-4 bg-muted animate-pulse rounded w-full" />
          </div>
        </div>
      </div>
    </div>
  )
}
