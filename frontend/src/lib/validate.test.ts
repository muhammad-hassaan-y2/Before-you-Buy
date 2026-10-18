import { describe, expect, it } from "vitest"

import { parseMetres, validateLink, validatePhoto, validateRoom } from "@/lib/validate"

describe("parseMetres", () => {
  it("reads dots and commas, rejects everything else", () => {
    expect(parseMetres(" 3.5 ")).toBe(3.5)
    expect(parseMetres("3,5")).toBe(3.5)
    for (const bad of ["", "abc", "3 m", "1e3", "-2", "."]) expect(parseMetres(bad)).toBeNull()
  })
})

describe("validateRoom", () => {
  it("returns the numbers when all three are fine", () => {
    expect(validateRoom({ width: "4", depth: "3.5", height: "2.4" })).toEqual({ room: { width: 4, depth: 3.5, height: 2.4 }, errors: {} })
  })
  it("names each wrong field", () => {
    const { room, errors } = validateRoom({ width: "abc", depth: "400", height: "2.4" })
    expect(room).toBeNull()
    expect(Object.keys(errors)).toEqual(["width", "depth"])
  })
})

describe("validateLink", () => {
  it("accepts empty and real URLs, rejects the rest", () => {
    expect(validateLink("")).toBeNull()
    expect(validateLink("https://www.ikea.com/sofa")).toBeNull()
    expect(validateLink("not a link")).not.toBeNull()
    expect(validateLink("ftp://x.com/a")).not.toBeNull()
  })
})

describe("validatePhoto", () => {
  it("wants a reasonably small image", () => {
    expect(validatePhoto({ type: "image/png", size: 1000 })).toBeNull()
    expect(validatePhoto({ type: "application/pdf", size: 1000 })).not.toBeNull()
    expect(validatePhoto({ type: "image/jpeg", size: 13 * 1024 * 1024 })).not.toBeNull()
  })
})
