/**
 * Curated high-resolution studio furniture photography.
 * Each image is an authentic, high-quality photograph optimized with Unsplash CDN.
 */

export type ProductImageData = {
  url: string
  alt: string
  color: string
}

const CATEGORY_FALLBACKS: Record<string, ProductImageData> = {
  sofa: {
    url: "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=1200&q=85",
    alt: "Modern comfortable sofa in minimalist living room",
    color: "#2c3e50",
  },
  sectional: {
    url: "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&q=85",
    alt: "Contemporary L-shaped sectional couch with clean lines",
    color: "#34495e",
  },
  armchair: {
    url: "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&q=85",
    alt: "Scandinavian designer armchair with timber frame",
    color: "#d4a373",
  },
  ottoman: {
    url: "https://images.unsplash.com/photo-1580481077114-1e033ca07309?auto=format&fit=crop&w=1200&q=85",
    alt: "Minimalist upholstered footstool ottoman",
    color: "#7f8c8d",
  },
  table: {
    url: "https://images.unsplash.com/photo-1615066390971-03e4e1c36ddf?auto=format&fit=crop&w=1200&q=85",
    alt: "Solid timber dining table in bright modern interior",
    color: "#b08968",
  },
  desk: {
    url: "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?auto=format&fit=crop&w=1200&q=85",
    alt: "Minimalist modern home office desk",
    color: "#333333",
  },
  bed: {
    url: "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=85",
    alt: "Elegant modern platform bed with textured linens",
    color: "#e9ecef",
  },
  wardrobe: {
    url: "https://images.unsplash.com/photo-1558997519-83ea9252def8?auto=format&fit=crop&w=1200&q=85",
    alt: "Built-in minimalist wardrobe storage system",
    color: "#f8f9fa",
  },
  bookcase: {
    url: "https://images.unsplash.com/photo-1594980596870-8aa52a78d8cd?auto=format&fit=crop&w=1200&q=85",
    alt: "Architectural modern wooden bookcase shelving",
    color: "#9c6644",
  },
  shelf: {
    url: "https://images.unsplash.com/photo-1598300042247-d088f8ab3a91?auto=format&fit=crop&w=1200&q=85",
    alt: "Modular cube shelving storage unit",
    color: "#6c757d",
  },
  sideboard: {
    url: "https://images.unsplash.com/photo-1538688525198-9b88f6f53126?auto=format&fit=crop&w=1200&q=85",
    alt: "Mid-century modern oak sideboard credenza",
    color: "#a68a64",
  },
  "tv unit": {
    url: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=85",
    alt: "Low-profile minimalist television bench and media console",
    color: "#212529",
  },
  cabinet: {
    url: "https://images.unsplash.com/photo-1595428774223-ef52624120d2?auto=format&fit=crop&w=1200&q=85",
    alt: "Clean drawer cabinet and bedside nightstand",
    color: "#adb5bd",
  },
  rug: {
    url: "https://images.unsplash.com/photo-1600121848594-d8644e57abab?auto=format&fit=crop&w=1200&q=85",
    alt: "Textured woven wool area rug on parquet floor",
    color: "#e2e8f0",
  },
  stool: {
    url: "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=1200&q=85",
    alt: "Curved natural birch stool",
    color: "#ddb892",
  },
}

const SKU_IMAGES: Record<string, ProductImageData> = {
  // Sofas & Sectionals
  "SOFA-201": {
    url: "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=1200&q=85",
    alt: "Kivik 2-seat sofa in deep emerald fabric",
    color: "#2f4858",
  },
  "SOFA-301": {
    url: "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&q=85",
    alt: "Kivik 3-seat sofa in soft tailored charcoal upholstery",
    color: "#333a42",
  },
  "SOFA-302": {
    url: "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&q=85",
    alt: "Ektorp 3-seat sofa in natural washed Belgian linen",
    color: "#dcd6cd",
  },
  "SOFA-401": {
    url: "https://images.unsplash.com/photo-1618221195710-dd6b41faaea6?auto=format&fit=crop&w=1200&q=85",
    alt: "Soderhamn 4-seat modular sofa with deep comfortable seating",
    color: "#e4e5e7",
  },
  "SOFA-L10": {
    url: "https://images.unsplash.com/photo-1512212621149-107ffe572d2f?auto=format&fit=crop&w=1200&q=85",
    alt: "Kalltorp L-shaped sectional couch with corner chaise lounge",
    color: "#4a5568",
  },
  "SOFA-M01": {
    url: "https://images.unsplash.com/photo-1540574163026-643ea20ade25?auto=format&fit=crop&w=1200&q=85",
    alt: "Margret 2-seat sofa bed with foldout mechanism",
    color: "#5c6b73",
  },
  "SOFA-S11": {
    url: "https://images.unsplash.com/photo-1573866926487-a1865558a9cf?auto=format&fit=crop&w=1200&q=85",
    alt: "Sitskas modular 3-seat sofa in lush amber velour",
    color: "#b07d62",
  },

  // Armchairs & Stools
  "CHR-101": {
    url: "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?auto=format&fit=crop&w=1200&q=85",
    alt: "Poang cantilever armchair with curved bentwood birch frame",
    color: "#e9d8a6",
  },
  "CHR-102": {
    url: "https://images.unsplash.com/photo-1580481077114-1e033ca07309?auto=format&fit=crop&w=1200&q=85",
    alt: "Eames-style executive lounge chair in top-grain black leather",
    color: "#1a1a1a",
  },
  "CHR-103": {
    url: "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?auto=format&fit=crop&w=1200&q=85",
    alt: "Strandmon wing armchair with button-tufted backrest",
    color: "#8338ec",
  },
  "CHR-104": {
    url: "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=1200&q=85",
    alt: "Loshi contemporary rocking chair with warm timber skids",
    color: "#d4a373",
  },
  "OTT-201": {
    url: "https://images.unsplash.com/photo-1580481077114-1e033ca07309?auto=format&fit=crop&w=1200&q=85",
    alt: "Klippan tailored ottoman footstool",
    color: "#495057",
  },
  "STO-101": {
    url: "https://images.unsplash.com/photo-1503602642458-232111445657?auto=format&fit=crop&w=1200&q=85",
    alt: "Alnatorp solid birch minimalist stool",
    color: "#e6ccb2",
  },

  // Tables & Desks
  "TAB-101": {
    url: "https://images.unsplash.com/photo-1615066390971-03e4e1c36ddf?auto=format&fit=crop&w=1200&q=85",
    alt: "Ekenset glass and metal dining table",
    color: "#4a5568",
  },
  "TAB-102": {
    url: "https://images.unsplash.com/photo-1530018607912-eff2daa1bac4?auto=format&fit=crop&w=1200&q=85",
    alt: "Malsjelvi extending dining table in solid white oak",
    color: "#ddb892",
  },
  "TAB-103": {
    url: "https://images.unsplash.com/photo-1577140917170-285929fb55b7?auto=format&fit=crop&w=1200&q=85",
    alt: "Ingatorp 180 solid Scandinavian pine dining table",
    color: "#b08968",
  },
  "TAB-201": {
    url: "https://images.unsplash.com/photo-1533090161767-e6ffed986c88?auto=format&fit=crop&w=1200&q=85",
    alt: "Lack square minimalist side table",
    color: "#ffffff",
  },
  "TAB-301": {
    url: "https://images.unsplash.com/photo-1532372320572-cda25653a26d?auto=format&fit=crop&w=1200&q=85",
    alt: "Stenheden low profile oak coffee table",
    color: "#c68b59",
  },
  "TAB-401": {
    url: "https://images.unsplash.com/photo-1544457070-4cd773b4d71e?auto=format&fit=crop&w=1200&q=85",
    alt: "Burdet round dining table in pale birch",
    color: "#ede0d4",
  },
  "DESK-101": {
    url: "https://images.unsplash.com/photo-1518455027359-f3f8164ba6bd?auto=format&fit=crop&w=1200&q=85",
    alt: "Bektet writing desk with integrated soft-close drawers",
    color: "#7f5539",
  },
  "DESK-102": {
    url: "https://images.unsplash.com/photo-1595515106969-1ce29566ff1c?auto=format&fit=crop&w=1200&q=85",
    alt: "Uppspeel motorized electric sit-stand height-adjustable desk",
    color: "#111827",
  },

  // Beds
  "BED-101": {
    url: "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=85",
    alt: "Malm modern platform double bed in neutral bedroom",
    color: "#e2e8f0",
  },
  "BED-102": {
    url: "https://images.unsplash.com/photo-1540518614846-7ede433c4ef0?auto=format&fit=crop&w=1200&q=85",
    alt: "Tarva solid oak king size bed frame with slatted headboard",
    color: "#b08968",
  },
  "BED-103": {
    url: "https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?auto=format&fit=crop&w=1200&q=85",
    alt: "Slatthall minimalist solid pine single bed frame",
    color: "#e6ccb2",
  },
  "BED-104": {
    url: "https://images.unsplash.com/photo-1505693314120-0d443867891c?auto=format&fit=crop&w=1200&q=85",
    alt: "Nemom low Japanese-style oak veneer platform bed",
    color: "#7f5539",
  },

  // Wardrobes & Storage
  "WRD-101": {
    url: "https://images.unsplash.com/photo-1558997519-83ea9252def8?auto=format&fit=crop&w=1200&q=85",
    alt: "Pax two-door wardrobe with smooth frosted glass sliding doors",
    color: "#f8f9fa",
  },
  "WRD-102": {
    url: "https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=1200&q=85",
    alt: "Pax full-height 4-door wardrobe with modular internal organizers",
    color: "#e9ecef",
  },
  "WRD-103": {
    url: "https://images.unsplash.com/photo-1595428774223-ef52624120d2?auto=format&fit=crop&w=1200&q=85",
    alt: "Brimnes 3-door wardrobe with full-length integrated mirror",
    color: "#ffffff",
  },
  "BCK-101": {
    url: "https://images.unsplash.com/photo-1594980596870-8aa52a78d8cd?auto=format&fit=crop&w=1200&q=85",
    alt: "Billy tall bookcase shelving unit in pale Scandinavian birch",
    color: "#e6ccb2",
  },
  "BCK-102": {
    url: "https://images.unsplash.com/photo-1598300042247-d088f8ab3a91?auto=format&fit=crop&w=1200&q=85",
    alt: "Eketorp slim vertical bookcase with solid oak shelves",
    color: "#9c6644",
  },
  "BCK-103": {
    url: "https://images.unsplash.com/photo-1544457070-4cd773b4d71e?auto=format&fit=crop&w=1200&q=85",
    alt: "Kallax 4x2 open modular cube room divider shelf",
    color: "#ffffff",
  },
  "SBD-101": {
    url: "https://images.unsplash.com/photo-1538688525198-9b88f6f53126?auto=format&fit=crop&w=1200&q=85",
    alt: "Herrevad mid-century modern solid oak sideboard credenza",
    color: "#7f5539",
  },
  "TVU-101": {
    url: "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=85",
    alt: "Besto clean low-profile television bench media console",
    color: "#1f2937",
  },
  "CAB-101": {
    url: "https://images.unsplash.com/photo-1595428774223-ef52624120d2?auto=format&fit=crop&w=1200&q=85",
    alt: "Helmer industrial powder-coated steel drawer filing cabinet",
    color: "#374151",
  },
  "CAB-102": {
    url: "https://images.unsplash.com/photo-1532372320572-cda25653a26d?auto=format&fit=crop&w=1200&q=85",
    alt: "Rast natural solid pine compact bedside nightstand",
    color: "#e6ccb2",
  },
  "RUG-101": {
    url: "https://images.unsplash.com/photo-1600121848594-d8644e57abab?auto=format&fit=crop&w=1200&q=85",
    alt: "Rindar short-pile plush area rug with subtle geometric texture",
    color: "#cbd5e1",
  },
}

/**
 * Returns studio photography and metadata for a SKU, with category fallback.
 */
export function getProductImage(sku?: string | null, category?: string | null): ProductImageData {
  const normalizedSku = sku ? sku.trim().toUpperCase() : ""
  if (normalizedSku && SKU_IMAGES[normalizedSku]) {
    return SKU_IMAGES[normalizedSku]
  }

  const normalizedCategory = category ? category.trim().toLowerCase() : ""
  if (normalizedCategory && CATEGORY_FALLBACKS[normalizedCategory]) {
    return CATEGORY_FALLBACKS[normalizedCategory]
  }

  return {
    url: "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?auto=format&fit=crop&w=1200&q=85",
    alt: "Modern Scandinavian interior piece",
    color: "#1e293b",
  }
}
