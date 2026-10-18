import Link from "next/link"

export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-24">
      <p className="eyebrow text-primary">404</p>
      <h1 className="display mt-4 text-5xl text-balance">That page is not on the plan.</h1>
      <p className="mt-4 max-w-md text-muted-foreground">The address does not match anything in the shop. Go back to the shelf and measure from there.</p>
      <Link href="/store" className="mt-8 inline-flex h-12 items-center rounded-full bg-foreground px-7 text-sm font-medium text-background transition-colors hover:bg-foreground/85">
        Back to the shop
      </Link>
    </div>
  )
}
