"use client"

import { Bot, Loader2, Send, User } from "lucide-react"
import { useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { chat, type ChatReply } from "@/lib/agent"

type Turn = { role: "user" | "assistant"; content: string; answeredBy?: string }

const OPENERS = ["Will a 220 cm sofa fit a 4 × 3.5 m room?", "What walkway do you check before saying it fits?", "Which SKU in the catalog fits a narrow bedroom?"]

export function AgentChat() {
  const [turns, setTurns] = useState<Turn[]>([])
  const [draft, setDraft] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const conversation = useRef<string | undefined>(undefined)

  async function send(text: string) {
    const message = text.trim()
    if (!message || busy) return
    setBusy(true)
    setError(null)
    setTurns((current) => [...current, { role: "user", content: message }])
    setDraft("")
    try {
      const history = [...turns, { role: "user", content: message }].map((turn) => ({ role: turn.role, content: turn.content }))
      const reply: ChatReply = await chat(history, conversation.current)
      conversation.current = reply.conversation_id ?? conversation.current
      setTurns((current) => [...current, { role: "assistant", content: reply.answer, answeredBy: reply.answered_by }])
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The agent did not answer.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ask about a fit
        </CardTitle>
        <CardDescription>
Each answer says who replied.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex min-h-36 flex-col gap-3 rounded-lg border bg-muted/20 p-3 text-sm">
          {turns.length === 0 &&
            OPENERS.map((opener) => (
              <Button key={opener} type="button" variant="ghost" size="sm" className="justify-start text-muted-foreground" disabled={busy} onClick={() => send(opener)}>
                {opener}
              </Button>
            ))}

          {turns.map((turn, index) => (
            <div key={index} className={turn.role === "user" ? "flex flex-col items-end gap-1" : "flex flex-col items-start gap-1"}>
              <div
                className={
                  turn.role === "user"
                    ? "max-w-[85%] rounded-lg rounded-br-sm bg-primary px-3 py-2 text-primary-foreground"
                    : "max-w-[85%] whitespace-pre-line rounded-lg rounded-bl-sm border bg-background px-3 py-2"
                }
              >
                {turn.content}
              </div>
              {turn.answeredBy && (
                <Badge variant="outline" className="text-[10px]">
                  {turn.answeredBy.includes("evolus") ? "Evolus agent" : turn.answeredBy}
                </Badge>
              )}
            </div>
          ))}

          {busy && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="size-3 animate-spin" /> thinking…
            </p>
          )}
        </div>

        {error && <p className="flex items-center gap-2 text-sm text-destructive">{error}</p>}

        <form
          className="flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault()
            void send(draft)
          }}
        >
          <div className="relative flex-1">
            <Label htmlFor="agent-chat" className="sr-only">
              Ask about a piece, a room or a verdict
            </Label>
            <Textarea
              id="agent-chat"
              rows={2}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault()
                  if (draft.trim() && !busy) {
                    void send(draft)
                  }
                }
              }}
              placeholder="Ask about a piece, a room or a verdict (Shift+Enter for newline)"
              disabled={busy}
              className="min-h-[56px] resize-none pr-3"
            />
          </div>
          <Button type="submit" className="h-10 self-end sm:self-auto" disabled={busy || !draft.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : <Send className="size-4" />}
            <span className="sr-only">Send</span>
          </Button>
        </form>

        <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <User className="size-3" /> Answers are grounded in the catalog and the geometry worker, not in a model guessing.
        </p>
      </CardContent>
    </Card>
  )
}
