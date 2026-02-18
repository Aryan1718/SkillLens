import type { ReactNode } from 'react'

interface MarkdownContentProps {
  content: string
}

function flushParagraph(buffer: string[]): ReactNode | null {
  if (buffer.length === 0) {
    return null
  }
  const text = buffer.join(' ').trim()
  buffer.length = 0
  if (!text) {
    return null
  }
  return <p>{text}</p>
}

function renderInlineCode(text: string): ReactNode[] {
  const parts = text.split('`')
  return parts.map((part, index) => {
    if (index % 2 === 1) {
      return <code key={`${part}-${index}`}>{part}</code>
    }
    return <span key={`${part}-${index}`}>{part}</span>
  })
}

export function MarkdownContent({ content }: MarkdownContentProps) {
  const lines = content.split(/\r?\n/)
  const nodes: ReactNode[] = []
  const paragraphBuffer: string[] = []
  let listItems: string[] = []
  let inCodeBlock = false
  let codeLines: string[] = []

  function flushList() {
    if (listItems.length > 0) {
      const current = listItems
      listItems = []
      nodes.push(
        <ul key={`list-${nodes.length}`}>
          {current.map((item, idx) => (
            <li key={`${item}-${idx}`}>{renderInlineCode(item)}</li>
          ))}
        </ul>
      )
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()

    if (line.startsWith('```')) {
      const paragraph = flushParagraph(paragraphBuffer)
      if (paragraph) nodes.push(paragraph)
      flushList()

      if (inCodeBlock) {
        nodes.push(
          <pre key={`code-${nodes.length}`}>
            <code>{codeLines.join('\n')}</code>
          </pre>
        )
        codeLines = []
      }
      inCodeBlock = !inCodeBlock
      continue
    }

    if (inCodeBlock) {
      codeLines.push(rawLine)
      continue
    }

    if (!line) {
      const paragraph = flushParagraph(paragraphBuffer)
      if (paragraph) nodes.push(paragraph)
      flushList()
      continue
    }

    if (line.startsWith('# ')) {
      const paragraph = flushParagraph(paragraphBuffer)
      if (paragraph) nodes.push(paragraph)
      flushList()
      nodes.push(<h2 key={`h2-${nodes.length}`}>{line.replace('# ', '')}</h2>)
      continue
    }

    if (line.startsWith('## ')) {
      const paragraph = flushParagraph(paragraphBuffer)
      if (paragraph) nodes.push(paragraph)
      flushList()
      nodes.push(<h3 key={`h3-${nodes.length}`}>{line.replace('## ', '')}</h3>)
      continue
    }

    if (/^[-*]\s+/.test(line)) {
      const paragraph = flushParagraph(paragraphBuffer)
      if (paragraph) nodes.push(paragraph)
      listItems.push(line.replace(/^[-*]\s+/, ''))
      continue
    }

    flushList()
    paragraphBuffer.push(line)
  }

  const paragraph = flushParagraph(paragraphBuffer)
  if (paragraph) nodes.push(paragraph)
  flushList()

  if (inCodeBlock && codeLines.length > 0) {
    nodes.push(
      <pre key={`code-${nodes.length}`}>
        <code>{codeLines.join('\n')}</code>
      </pre>
    )
  }

  if (nodes.length === 0) {
    return <p>No markdown content found.</p>
  }

  return <>{nodes}</>
}
