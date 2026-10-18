/** A drawn floor plan for the hero: a sofa, the walkway to the balcony and the door swing. It is an
 *  illustration of what the shop measures, not a result, and says so. Colours come from the theme. */
export function HeroPlan() {
  return (
    <figure className="relative mx-auto w-full max-w-md">
      <div className="rounded-3xl border border-border bg-card p-4 shadow-xl shadow-black/5">
        <svg viewBox="0 0 400 300" role="img" aria-label="Illustration: a three-seat sofa in a room with a walkway to the balcony kept clear" className="h-auto w-full">
          <defs>
            <pattern id="hero-grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path d="M20 0H0V20" fill="none" className="stroke-border" strokeWidth="1" />
            </pattern>
          </defs>
          <rect x="10" y="10" width="380" height="280" rx="10" fill="url(#hero-grid)" className="stroke-muted-foreground/50" strokeWidth="3" />
          {/* door swing */}
          <path d="M10 290 L10 230 A60 60 0 0 1 70 290 Z" className="fill-primary/10 stroke-primary/50" strokeDasharray="4 4" />
          <text x="22" y="276" className="fill-muted-foreground" fontSize="10">door</text>
          {/* balcony opening */}
          <rect x="386" y="70" width="8" height="110" rx="2" className="fill-primary/60" />
          <text x="300" y="60" className="fill-muted-foreground" fontSize="10">balcony</text>
          {/* walkway */}
          <path d="M100 250 C200 250 260 190 380 125" fill="none" className="stroke-success" strokeWidth="3" strokeDasharray="2 8" strokeLinecap="round" />
          {/* sofa */}
          <g>
            <rect x="110" y="70" width="150" height="62" rx="10" className="fill-primary/20 stroke-primary" strokeWidth="2.5" />
            <rect x="118" y="78" width="134" height="22" rx="6" className="fill-primary/30" />
            <text x="185" y="122" textAnchor="middle" className="fill-foreground" fontSize="11" fontWeight="600">3-seat sofa · 220 cm</text>
          </g>
          {/* clearance */}
          <path d="M110 150 H260" className="stroke-success" strokeWidth="1.5" />
          <path d="M110 145 V155 M260 145 V155" className="stroke-success" strokeWidth="1.5" />
          <text x="185" y="168" textAnchor="middle" className="fill-success" fontSize="11" fontWeight="600">walkway 0.89 m</text>
        </svg>
      </div>
      <figcaption className="eyebrow mt-3 text-center text-muted-foreground">Illustration · every real verdict comes from the geometry engine</figcaption>
    </figure>
  )
}
