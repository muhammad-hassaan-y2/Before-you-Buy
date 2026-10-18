"use client"

import { ImageIcon, X } from "lucide-react"
import { useEffect, useId, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { validatePhoto } from "@/lib/validate"
import { cn } from "@/lib/utils"

type Props = {
  file: File | null
  onFile: (file: File | null) => void
  disabled?: boolean
  hint?: string
}

/** A photo target that takes a drop, a click or the keyboard. Drag state is counted rather than
 *  toggled, because dragleave also fires when the pointer crosses a child; and while a file is
 *  being dragged the page itself is told not to open it, so a near miss does not navigate away. */
export function PhotoDropzone({ file, onFile, disabled, hint = "Drop a JPG or PNG here, or click to choose" }: Props) {
  const inputId = useId()
  const input = useRef<HTMLInputElement>(null)
  const depth = useRef(0)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const swallow = (event: DragEvent) => {
      if (event.dataTransfer?.types.includes("Files")) event.preventDefault()
    }
    window.addEventListener("dragover", swallow)
    window.addEventListener("drop", swallow)
    return () => {
      window.removeEventListener("dragover", swallow)
      window.removeEventListener("drop", swallow)
    }
  }, [])

  function accept(next: File | undefined) {
    if (!next) return
    const problem = validatePhoto(next)
    setError(problem)
    if (!problem) onFile(next)
  }

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label="Room photo"
        onClick={() => !disabled && input.current?.click()}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault()
            if (!disabled) input.current?.click()
          }
        }}
        onDragEnter={(event) => {
          event.preventDefault()
          depth.current += 1
          if (!disabled) setDragging(true)
        }}
        onDragOver={(event) => {
          event.preventDefault()
          event.dataTransfer.dropEffect = disabled ? "none" : "copy"
        }}
        onDragLeave={() => {
          depth.current = Math.max(0, depth.current - 1)
          if (depth.current === 0) setDragging(false)
        }}
        onDrop={(event) => {
          event.preventDefault()
          depth.current = 0
          setDragging(false)
          if (!disabled) accept(event.dataTransfer.files?.[0])
        }}
        className={cn(
          "flex min-h-20 cursor-pointer items-center justify-center gap-3 rounded-xl border-2 border-dashed px-4 py-4 text-center text-sm transition-colors",
          "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none",
          dragging ? "border-primary bg-primary/10" : file ? "border-primary/50 bg-primary/5" : "border-input hover:border-ring hover:bg-muted/40",
          disabled && "cursor-not-allowed opacity-50",
        )}
      >
        <ImageIcon className="size-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 truncate text-muted-foreground">{dragging ? "Release to use this photo" : file ? file.name : hint}</span>
        <input
          id={inputId}
          ref={input}
          type="file"
          accept="image/*"
          aria-label="Photo of the room"
          tabIndex={-1}
          className="sr-only"
          disabled={disabled}
          onClick={(event) => event.stopPropagation()}
          onChange={(event) => {
            accept(event.target.files?.[0])
            event.target.value = ""
          }}
        />
      </div>
      {error && (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
      {file && (
        <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => (setError(null), onFile(null))}>
          <X className="size-3.5" /> Remove
        </Button>
      )}
    </div>
  )
}
