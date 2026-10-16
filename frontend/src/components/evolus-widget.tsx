"use client"

import Script from "next/script"
import { createElement } from "react"

/**
 * The Evolus chat widget: one script tag, straight from the workspace.
 *
 * `NEXT_PUBLIC_EVOLUS_WIDGET_URL` is the src the workspace hands you. `NEXT_PUBLIC_EVOLUS_WIDGET_SCRIPT`
 * is optional and names the custom element for widgets that mount on a tag instead of creating their
 * own launcher. With neither set the page renders no widget at all, so a local clone stays clean.
 */
const url = process.env.NEXT_PUBLIC_EVOLUS_WIDGET_URL ?? ""
const mount = process.env.NEXT_PUBLIC_EVOLUS_WIDGET_SCRIPT ?? ""

export function EvolusWidget() {
  if (!/^https:\/\//.test(url)) return null
  const launcher = /^[a-z][a-z0-9]*(-[a-z0-9]+)+$/.test(mount) ? createElement(mount) : null

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-end p-4 [&>*]:pointer-events-auto">
      <Script src={url} strategy="afterInteractive" />
      {launcher}
    </div>
  )
}
