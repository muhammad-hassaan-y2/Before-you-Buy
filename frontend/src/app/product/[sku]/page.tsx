import type { Metadata } from "next"

import { ProductDetail } from "@/components/product-detail"

type Props = { params: Promise<{ sku: string }> }

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { sku } = await params
  return {
    title: `${sku} · Buy You Before`,
    description: "Dropship terms for this piece, and a live fit simulation against the room you describe.",
  }
}

export default async function ProductPage({ params }: Props) {
  const { sku } = await params
  return <ProductDetail sku={decodeURIComponent(sku)} />
}
