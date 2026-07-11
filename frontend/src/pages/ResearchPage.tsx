import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  toolCalls?: { tool: string; input: Record<string, unknown> }[]
}

const SUGGESTIONS = [
  'Give me a full research readout on Parag Parikh Flexi Cap',
  'Compare the top mid cap funds by risk-adjusted returns',
  'What do we know about R. Srinivasan as a fund manager?',
  'Which flexi cap funds have the best consistency?',
]

export default function ResearchPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, busy])

  const send = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    const next: ChatMsg[] = [...messages, { role: 'user', content: trimmed }]
    setMessages(next)
    setInput('')
    setBusy(true)
    setError(null)
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: next.map(({ role, content }) => ({ role, content })),
        }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => null)
        throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`)
      }
      const data = await res.json()
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: data.reply, toolCalls: data.tool_calls },
      ])
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="research">
      {messages.length === 0 && (
        <div className="search-hero" style={{ paddingBottom: 8 }}>
          <p className="eyebrow">Research assistant</p>
          <h1>Ask the desk.</h1>
          <p>
            Every number in the answer is pulled live from the fund database — nothing is
            quoted from model memory. Not investment advice.
          </p>
          <div className="cat-strip">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => send(s)} disabled={busy}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="chat-log">
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className="who">{m.role === 'user' ? 'You' : 'Kosh'}</div>
            {m.toolCalls && m.toolCalls.length > 0 && (
              <div className="tool-trail">
                {m.toolCalls.map((t, j) => (
                  <span key={j} className="tool-chip mono">
                    {t.tool}
                  </span>
                ))}
              </div>
            )}
            <div className="bubble">
              {m.role === 'assistant' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        {busy && <div className="state-note">Checking the books…</div>}
        {error && <div className="state-note error">{error}</div>}
        <div ref={endRef} />
      </div>

      <form
        className="search-box chat-input"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about any fund, category, or manager…"
          aria-label="Ask the research assistant"
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          {busy ? '…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}
