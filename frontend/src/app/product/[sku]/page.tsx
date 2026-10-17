import type { Metadata } from "next"

import { ProductDetail } from "@/components/product-detail"

type Props = { params: Promise<{ sku: string }> }

/** The SKU is URL data, and everything under this page is fetched in the browser, so there is no
 *  shell worth resolving ahead of the click — the route is allowed to block on the param. */
export const instant = false

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { sku } = await params
  return {
    title: sku,
    description: "Dropship terms for this piece, and a live fit simulation against the room you describe.",
  }
}

export default async function ProductPage({ params }: Props) {
  const { sku } = await params
  return <ProductDetail sku={decodeURIComponent(sku)} />
}
