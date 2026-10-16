import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { DimensionEstimateWarning, ProductSourceBadge } from "@/components/product-provenance"
import type { ProductProfile } from "@/lib/api"

const profile = (over: Partial<ProductProfile> = {}): ProductProfile => ({
  name: "Linen three-seater sofa",
  category: "sofa",
  geometry: { width_cm: 220, depth_cm: 95, height_cm: 85, clearance_cm: 60 },
  confidence: 0.45,
  summary: "Read from the listing.",
  source: "heuristic",
  ...over,
})

describe("ProductSourceBadge", () => {
  it("names the AMD model behind a Token Factory read", () => {
    render(<ProductSourceBadge profile={profile({ source: "amd_token_factory" })} />)
    expect(screen.getByText("AMD Token Factory")).toBeInTheDocument()
  })

  it("keeps a label for rows written before the provider was named", () => {
    render(<ProductSourceBadge profile={profile({ source: "vllm" })} />)
    expect(screen.getByText("vLLM")).toBeInTheDocument()
  })

  it("shows an unknown source rather than hiding it", () => {
    render(<ProductSourceBadge profile={profile({ source: "merchant_feed" })} />)
    expect(screen.getByText("merchant_feed")).toBeInTheDocument()
  })
})

describe("DimensionEstimateWarning", () => {
  it("stays silent when the SKU published every size", () => {
    render(
      <DimensionEstimateWarning
        profile={profile({
          source: "catalog",
          dimension_reliability: { width_cm: "verified", depth_cm: "verified", height_cm: "verified" },
        })}
      />,
    )
    expect(screen.queryByText(/estimated|guess/)).not.toBeInTheDocument()
  })

  it("stays silent when Token Factory read all three axes off the listing", () => {
    render(
      <DimensionEstimateWarning
        profile={profile({
          source: "amd_token_factory",
          dimension_reliability: { width_cm: "extracted", depth_cm: "extracted", height_cm: "extracted" },
        })}
      />,
    )
    expect(screen.queryByText(/estimated|guess/)).not.toBeInTheDocument()
  })

  it("names the single axis that was guessed", () => {
    render(
      <DimensionEstimateWarning
        profile={profile({
          dimension_reliability: { width_cm: "verified", depth_cm: "verified", height_cm: "estimated" },
          measurement_basis: "listing_partial",
        })}
      />,
    )
    expect(screen.getByText(/height is a category guess/)).toBeInTheDocument()
    expect(screen.getByText(/220 × 95 × 85 cm/)).toBeInTheDocument()
  })

  it("lists several guessed axes in words", () => {
    render(
      <DimensionEstimateWarning
        profile={profile({
          dimension_reliability: { width_cm: "estimated", depth_cm: "estimated", height_cm: "verified" },
          measurement_basis: "listing_partial",
        })}
      />,
    )
    expect(screen.getByText(/width and depth are a category guess/)).toBeInTheDocument()
  })

  it("says so when the whole box is a category default", () => {
    render(
      <DimensionEstimateWarning
        profile={profile({
          dimension_reliability: { width_cm: "estimated", depth_cm: "estimated", height_cm: "estimated" },
          measurement_basis: "category_estimate",
        })}
      />,
    )
    expect(screen.getByText(/None of these sizes came from the listing/)).toBeInTheDocument()
  })

  it("keeps the compact form short enough for a badge row", () => {
    render(
      <DimensionEstimateWarning
        profile={profile({ dimension_reliability: { height_cm: "estimated" } })}
        compact
      />,
    )
    expect(screen.getByText("height estimated")).toBeInTheDocument()
  })

  it("stays silent for rows that predate the reliability map", () => {
    render(<DimensionEstimateWarning profile={profile()} />)
    expect(screen.queryByText(/estimated|guess/)).not.toBeInTheDocument()
  })
})
