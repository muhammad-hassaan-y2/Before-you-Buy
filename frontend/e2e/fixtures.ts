/** Responses the two pages need to be tested without a backend.
 *  They mirror the pydantic contracts, so a drift between them is a failing test. */

export const tools = {
  tools: [
    { name: "catalog_search", description: "Find furniture in the shop's catalog by words, category or price band." },
    { name: "read_brief", description: "Turn a shopper's own words into a category, a price band and a room size." },
    {
      name: "simulate_product",
      description: "Measure one product against one room and wait for the fit verdict. Pass image_key to use a room measured from a photo.",
    },
    { name: "fit_report", description: "The verdict, placements and walkways for a simulation already run." },
    {
      name: "explain_fit",
      description: "Read a fit report back in words: the facts behind the verdict and what to change.",
    },
    {
      name: "joint_fit",
      description: "Judge two or more pieces as one purchase, measuring each and combining the footprints.",
    },
    { name: "find_alternatives", description: "Pieces in the same category that are no wider, each tested against the room." },
    {
      name: "fit_catalog",
      description:
        "Which of the shop's pieces actually fit this room, measured in parallel and split into fits, does-not-fit and unproven.",
    },
    { name: "proven_fit_offer", description: "An agent-readable offer that only a proven fit can back." },
    {
      name: "reserve_fit",
      description: "Hold a proven-fitting piece, gated behind the shopper's own confirmation; the MCP door asks them in their own client when it can.",
    },
    { name: "returns_estimate", description: "What a fit check is worth, as arithmetic over stated assumptions." },
    { name: "add_to_cart", description: "Put a piece in the bag at the shop's own listed price, with the fit proof attached when one exists." },
    { name: "view_cart", description: "What is in the bag, what it costs the shopper and the shop, and which lines are still unproven." },
    { name: "remove_from_cart", description: "Take one piece out of the bag." },
    {
      name: "measure_cart",
      description: "Measure what is in the bag against its room, and judge the pieces together as one purchase.",
    },
    { name: "checkout", description: "Turn a bag of proven fits into an order draft - on the shopper's own yes, and on nothing less." },
    { name: "order_status", description: "One order draft, with the fit proofs and the words that let it be placed." },
    {
      name: "start_journey",
      description: "Run the whole fit-assurance process for a shopper brief, against a photo-measured room when image_key is given.",
    },
    { name: "journey_status", description: "The trace of a journey, including the final decision." },
  ],
}

/** What agent-service says about its own connector. A local run has no public address, which is
 *  exactly the case the page has to explain rather than hide. */
export const connect = {
  name: "buy-you-before",
  title: "Buy You Before fit assurance",
  url: "/mcp/",
  transport: "streamable-http",
  public: false,
  mode: "stateless",
  elicitation: false,
  auth: {
    type: "none",
    header: null,
    works_in: ["chatgpt", "claude.ai", "claude-code", "cursor", "evolus"],
    does_not_work_in: [],
    why: "Anyone with the URL can spend the shop's GPU jobs, so this is a demo setting.",
  },
  capabilities: {
    tools: ["catalog_search", "fit_catalog", "reserve_fit"],
    resources: ["byb://catalog", "byb://fit/{simulation_id}", "byb://run/{run_id}"],
    prompts: ["fit-my-room", "hold-the-fit"],
  },
  clients: {
    chatgpt: {
      label: "ChatGPT (web)",
      requires_https: true,
      steps: [
        "Set PUBLIC_BASE_URL to the https tunnel URL and restart agent-service.",
        "Open the Apps directory -> Advanced -> Add custom MCP server.",
        "Create it, then @-mention Buy You Before in a chat and give it a room to measure.",
      ],
      note: "ChatGPT will not accept a static bearer header.",
    },
    claude: {
      label: "Claude (claude.ai)",
      requires_https: true,
      steps: [
        "Open Customize -> Connectors, or Settings -> Connectors on the desktop app.",
        "Click + and choose Add custom connector.",
        "Connect it as-is, or set an OAuth Client ID under Advanced settings when the shop speaks OAuth.",
        "Switch the connector on inside the chat, then ask it which sofas fit the room.",
      ],
      note: "claude.ai takes an unauthenticated or OAuth URL; a typed key belongs to Claude Code.",
    },
    "claude-code": { label: "Claude Code", requires_https: false, command: "claude mcp add --transport http buy-you-before /mcp/" },
    cursor: { label: "Cursor", requires_https: false, config: { mcpServers: { "buy-you-before": { url: "/mcp/" } } } },
    evolus: { label: "Evolus Studio", requires_https: true, steps: ["Add an MCP connector and paste the URL."] },
  },
  wiring: { PUBLIC_BASE_URL: "the https origin a client can reach" },
}

export const journey = {
  id: "e2e-run-1",
  status: "done",
  brief: {
    raw: "three-seater sofa under 900",
    category: "sofa",
    price_band: "$$",
    budget_eur: 900,
    room_width_m: 4,
    room_depth_m: 3.5,
    room_height_m: 2.4,
    must_haves: ["linen"],
    confidence: 0.72,
    source: "evolus",
  },
  steps: [
    { index: 0, kind: "intake", status: "ok", detail: "three-seater sofa under 900", tool: null, group: null, iteration: 1, ms: 0, output: null },
    { index: 1, kind: "agent", status: "ok", detail: "handed to the Evolus agent", tool: "POST /v1/chat/completions", group: null, iteration: 1, ms: 640, output: null },
    { index: 2, kind: "brief", status: "ok", detail: "sofa · $$ · 900", tool: "evolus", group: null, iteration: 1, ms: 120, output: null },
    { index: 3, kind: "shortlist", status: "ok", detail: "4 candidates", tool: "GET /api/v1/catalog", group: null, iteration: 1, ms: 18, output: null },
    { index: 4, kind: "simulate", status: "ok", detail: "KURA fitted", tool: "POST /api/v1/simulations", group: "pass-1", iteration: 1, ms: 2800, output: null },
    { index: 5, kind: "fit", status: "ok", detail: "BYB-KURA-3S -> fits", tool: "geometry-service", group: "pass-1", iteration: 1, ms: 2400, output: { simulation_id: "sim-e2e-1" } },
    { index: 6, kind: "branch", status: "branch", detail: "no candidate cleared the walkway, widening the band", tool: null, group: null, iteration: 2, ms: 0, output: null },
    { index: 7, kind: "reply", status: "ok", detail: "drafted from the fit report", tool: "evolus", group: null, iteration: 2, ms: 700, output: null },
  ],
  attempts: [
    {
      sku: "BYB-KURA-3S",
      name: "KURA three-seat sofa",
      price_band: "$$",
      score: 0.82,
      simulation_id: "sim-e2e-1",
      status: "done",
      verdict: "fits",
      coverage_pct: 14.2,
      walkway_m: { left: 0.9, right: 0.75, front: 0.6, back: 0.2 },
      reason: null,
    },
    {
      sku: "BYB-VIDGA-2S",
      name: "VIDGA two-seat sofa",
      price_band: "$",
      score: 0.61,
      simulation_id: "sim-e2e-2",
      status: "done",
      verdict: "tight",
      coverage_pct: 19.8,
      walkway_m: { left: 0.4, right: 0.35, front: 0.25, back: 0.1 },
      reason: null,
    },
  ],
  decision: {
    action: "recommend",
    sku: "BYB-KURA-3S",
    simulation_id: "sim-e2e-1",
    confidence: 0.84,
    reason: "widest walkway of the four tested pieces",
    evidence: { verdict: "fits", coverage_pct: 14.2 },
  },
  reply: "The KURA three-seat sofa fits your room with 0.60 m left to walk in front of it.",
  evolus_execution_id: "exec-e2e-1",
  conversation_id: null,
  error: null,
}

/** The same journey taken with a photo of the room: vision measured it, and the trace says so. */
export const photoJourney = {
  ...journey,
  steps: [
    journey.steps[0],
    {
      index: 1,
      kind: "room",
      status: "ok",
      detail: "every candidate is fitted into the room measured from the shopper's photo, not the typed numbers",
      tool: null,
      group: null,
      iteration: 1,
      ms: 0,
      output: null,
    },
    ...journey.steps.slice(2).map((step, position) => ({ ...step, index: position + 2 })),
  ],
}

/** What `returns_estimate` answered for those inputs, taken off the live service on 2026-10-16. */
export const estimate = {
  tool: "returns_estimate",
  result: {
    orders_per_month: 1000,
    returns_per_month: 200,
    fit_driven_returns_per_month: 134,
    returns_prevented_per_month: 33.5,
    handling_saved_eur_per_month: 335.0,
    revenue_kept_eur_per_month: 25125.0,
    per_simulation_value_eur: 25.46,
    assumptions: {
      return_rate: 0.2,
      fit_driven_share_of_returns: 0.67,
      handling_cost_eur_per_return: 10.0,
      average_order_value_eur: 750.0,
      share_of_fit_returns_prevented: 0.25,
      note: "Band prices stand in for the merchant feed until it is wired; every input above can be overridden by the caller.",
    },
  },
}

export const reservations = [
  {
    id: "res-e2e-1",
    simulation_id: "sim-e2e-1",
    sku: "BYB-KURA-3S",
    name: "KURA three-seat sofa",
    verdict: "fits",
    confirmation: "yes, hold the KURA for me",
    status: "pending_merchant",
    created_at: "2026-10-16T09:12:00Z",
  },
]

/** Terms as catalog-service derives them for those exact boxes, read off `terms_for` on
 *  2026-10-17 — a fixture that disagreed with the service would let the shop quote a price
 *  nothing computes. */
export const catalog = [
  {
    sku: "BYB-KURA-3S",
    name: "KURA three-seat sofa",
    brand: "KURA",
    category: "sofa",
    material: "linen",
    price_band: "$$",
    geometry: { width_cm: 200, depth_cm: 90, height_cm: 44, clearance_cm: 10 },
    commerce: {
      currency: "EUR",
      retail_eur: 919.0,
      cost_eur: 515.0,
      margin_eur: 404.0,
      margin_pct: 44.0,
      volume_m3: 1.512,
      supplier: { name: "Porto Frame Works", region: "PT" },
      lead_days: 18,
      freight: "pallet",
      product_url: "https://shop.example.com/p/kura-kura-three-seat-sofa-bybkura3s/",
      basis: "derived from the SKU's price band, category and box size; no supplier feed connected",
    },
  },
  {
    sku: "BYB-BILLY-80",
    name: "BILLY bookcase 80 cm",
    brand: "BILLY",
    category: "bookcase",
    material: "oak veneer",
    price_band: "$",
    geometry: { width_cm: 80, depth_cm: 28, height_cm: 202, clearance_cm: 5 },
    commerce: {
      currency: "EUR",
      retail_eur: 399.0,
      cost_eur: 176.0,
      margin_eur: 223.0,
      margin_pct: 55.9,
      volume_m3: 0.4525,
      supplier: { name: "Silesia Board Mills", region: "PL" },
      lead_days: 15,
      freight: "pallet",
      product_url: "https://shop.example.com/p/billy-billy-bookcase-80-cm-bybbilly80/",
      basis: "derived from the SKU's price band, category and box size; no supplier feed connected",
    },
  },
]

/** What `fit_catalog` answered for a 4 × 3.5 m room: one clears the walkway, one does not. */
export const catalogFits = {
  tool: "fit_catalog",
  result: {
    room: { width_m: 4, depth_m: 3.5, height_m: 2.4, measured_from_photo: false },
    checked: 2,
    fits: [
      {
        sku: "BYB-KURA-3S",
        name: "KURA three-seat sofa",
        price_band: "$$",
        score: 0.81,
        simulation_id: "sim-e2e-1",
        status: "completed",
        verdict: "fits",
        coverage_pct: 12.4,
        walkway_m: { front: 0.6 },
        reason: null,
        ms: 2400,
        size_cm: { width_cm: 200, depth_cm: 90, height_cm: 84 },
        tightest_walkway_m: 0.6,
        verify: null,
      },
    ],
    does_not_fit: [
      {
        sku: "BYB-BILLY-80",
        name: "BILLY bookcase 80 cm",
        price_band: "$",
        score: 0.6,
        simulation_id: "sim-e2e-2",
        status: "completed",
        verdict: "too_large",
        coverage_pct: 0,
        walkway_m: {},
        reason: null,
        ms: 1900,
        size_cm: { width_cm: 80, depth_cm: 28, height_cm: 202 },
        tightest_walkway_m: null,
        verify: null,
      },
    ],
    unproven: [],
    note: "Only the geometry engine's own verdict is reported here.",
  },
}

/** A bag the service filled: one line, its price from the catalog's own terms, its verdict from
 *  the sweep that measured it. The browser keeps none of this — only the cart id. */
export const cart = {
  cart_id: "cart-e2e-1",
  room: { width_m: 4, depth_m: 3.5, height_m: 2.4 },
  lines: [
    {
      sku: "BYB-KURA-3S",
      name: "KURA three-seat sofa",
      quantity: 1,
      price_eur: 919,
      cost_eur: 515,
      lead_days: 18,
      freight: "pallet",
      volume_m3: 1.512,
      simulation_id: "sim-e2e-1",
      verdict: "fits",
      coverage_pct: 14.2,
      walkway_m: { front: 0.6, left: 0.9, right: 0.75, back: 0.2 },
      footprint_m2: 1.8,
      placement_proved: true,
      room: { width_m: 4, depth_m: 3.5, height_m: 2.4 },
      added_at: "2026-10-17T09:00:00Z",
    },
  ],
  items: 1,
  total_eur: 919,
  cost_eur: 515,
  margin_eur: 404,
  volume_m3: 1.512,
  lead_days: 18,
  freight: "pallet",
  unproven: [],
  set: null,
  checkout: {
    tool: "checkout",
    ready: true,
    needs: "the shopper's own confirmation words",
    how: "Ask the shopper plainly: shall I place this order? Then pass their own words as confirmation.",
    refuses: "a bag with any line the engine has not cleared, so measure_cart comes before it",
  },
  note: "Prices are the catalog's own listed terms. Nothing is charged here: checkout writes a draft a person at the shop accepts.",
}

/** The same bag after `measure_cart` judged the two pieces as one purchase. */
export const measuredCart = {
  ...cart,
  lines: [...cart.lines, { ...cart.lines[0], sku: "BYB-BILLY-80", name: "BILLY bookcase 80 cm", price_eur: 399, cost_eur: 176, lead_days: 15, volume_m3: 0.4525, simulation_id: "sim-e2e-2", verdict: "tight", footprint_m2: 0.224 }],
  items: 2,
  total_eur: 1318,
  cost_eur: 691,
  margin_eur: 627,
  set: {
    verdict: "tight",
    footprint_m2: 2.024,
    usable_area_m2: 13.6,
    coverage_pct: 14.9,
    tightest_walkway_m: 0.6,
    conflicts: ["The tightest walkway would be 0.6 m, under the 0.7 m a shopper has to reach the far side at."],
    footprint_estimated_from_listing: [],
    note: "Each piece was measured alone against this room; the set verdict adds the footprints and the walkways up, not a combined layout search.",
  },
}

/** The draft `checkout` wrote, with the proof behind every line. */
export const order = {
  id: "ord-e2e-1",
  cart_id: "cart-e2e-1",
  lines: measuredCart.lines,
  currency: "EUR",
  total_eur: 1318,
  cost_eur: 691,
  margin_eur: 627,
  volume_m3: 1.9645,
  lead_days: 18,
  freight: "pallet",
  confirmation: "yes, order both of them",
  confirmed_through: "typed by the shopper",
  status: "awaiting_merchant",
  created_at: "2026-10-17T09:04:00Z",
  proofs: [
    { sku: "BYB-KURA-3S", simulation_id: "sim-e2e-1", verdict: "fits", quantity: 1, tightest_walkway_m: 0.6, verify: "/api/v1/simulations/sim-e2e-1" },
    { sku: "BYB-BILLY-80", simulation_id: "sim-e2e-2", verdict: "tight", quantity: 1, tightest_walkway_m: 0.6, verify: "/api/v1/simulations/sim-e2e-2" },
  ],
  combined: measuredCart.set,
  room: { width_m: 4, depth_m: 3.5, height_m: 2.4 },
  next: "A person at the shop accepts or releases this draft. No card is taken and nothing ships from this service.",
}

/** What a bag with an unmeasured line looks like, and the refusal that comes with checking out. */
export const unprovenCart = { ...cart, lines: [{ ...cart.lines[0], simulation_id: null, verdict: null, walkway_m: {}, placement_proved: false, room: null }], unproven: ["BYB-KURA-3S"], checkout: { ...cart.checkout, ready: false } }

export const simulation = {
  id: "sim-e2e-1",
  status: "completed",
  created_at: "2026-10-16T00:00:00Z",
  updated_at: "2026-10-16T00:00:02Z",
  room_width_m: 4,
  room_depth_m: 3.5,
  room_height_m: 2.4,
  has_model: true,
  product_profile: {
    name: "KURA three-seat sofa",
    brand: "KURA",
    category: "sofa",
    material: "linen",
    price_band: "$$",
    geometry: { width_cm: 200, depth_cm: 90, height_cm: 84, clearance_cm: 10 },
    confidence: 0.9,
    summary: "Three seats, oak legs.",
    source: "catalog",
    provider: null,
    model: null,
    // A published SKU box: nothing here is a category guess.
    dimension_reliability: { width_cm: "verified", depth_cm: "verified", height_cm: "verified" },
    measurement_basis: "catalog_sku",
    parts: [{ label: "seat cushion", size_cm: [180, 80, 35], offset_cm: [0, 5, 27], tone: "upholstery" }],
  },
  room_scan: {
    width_m: 4,
    depth_m: 3.5,
    height_m: 2.4,
    obstacles: [{ label: "window recess", ring: [[0, 0], [1.2, 0], [1.2, 0.3], [0, 0.3]], height_m: 1.1, source: "photo" }],
    measured: true,
    method: "photo",
    confidence: 0.81,
  },
  fit_report: {
    room_area_m2: 14,
    usable_area_m2: 13.6,
    coverage_pct: 14.2,
    verdict: "fits",
    conflicts: [],
    obstacles: [{ label: "window recess", ring: [[0, 0], [1.2, 0], [1.2, 0.3], [0, 0.3]], height_m: 1.1, source: "photo" }],
    door_swing_m: 0.85,
    door_pass: "tight",
    walkway_connected: true,
    isolated_pockets: 0,
    fragile: true,
    tolerance_cm: 2,
    suggestions: ["Measure the doorway as well as the room: the box is inside 2 cm of the frame."],
    placements: [
      {
        label: "against the long wall",
        ring: [[1, 0.4], [3, 0.4], [3, 1.3], [1, 1.3]],
        area_m2: 1.8,
        footprint_m2: 1.8,
        fits: true,
        centre_x_m: 2,
        centre_y_m: 0.85,
        rotation_deg: 0,
        walkway_m: { left: 0.9, right: 0.75, front: 0.6, back: 0.2 },
      },
    ],
  },
  scene: {
    version: "1",
    room_width_m: 4,
    room_depth_m: 3.5,
    room_height_m: 2.4,
    walls: [{ label: "window recess", ring: [[0, 0], [1.2, 0], [1.2, 0.3], [0, 0.3]], height_m: 1.1, source: "photo" }],
    door_swing_m: 0.85,
    product_name: "KURA three-seat sofa",
    product_category: "sofa",
    parts: [
      { label: "plinth", size_cm: [200, 90, 10], offset_cm: [0, 0, 5], tone: "leg" },
      { label: "seat cushion", size_cm: [180, 80, 35], offset_cm: [0, 5, 27], tone: "upholstery" },
      { label: "backrest", size_cm: [180, 20, 39], offset_cm: [0, -35, 64], tone: "upholstery" },
    ],
    geometry: { width_cm: 200, depth_cm: 90, height_cm: 84, clearance_cm: 10 },
    clearance_m: 0.1,
    placements: [
      { label: "against the long wall", fits: true, position_m: [2, 0, 0.85], rotation_deg: 0, walkway_m: { left: 0.9, right: 0.75, front: 0.6, back: 0.2 } },
      { label: "by the window", fits: false, position_m: [1, 0, 2.6], rotation_deg: 90, walkway_m: { left: 0.3, right: 0.2, front: 0.15, back: 0.4 } },
    ],
    cameras: [
      { label: "overview", position_m: [5.8, 3.6, -2.28], target_m: [2, 0.45, 1.75], fov_deg: 45 },
      { label: "first-person", position_m: [2, 1.62, 0.3], target_m: [2, 1.15, 3.5], fov_deg: 62 },
    ],
    verdict: "fits",
    coverage_pct: 14.2,
  },
}
