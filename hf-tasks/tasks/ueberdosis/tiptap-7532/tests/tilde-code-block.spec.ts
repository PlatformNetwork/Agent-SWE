import { Document } from '@tiptap/extension-document'
import { Paragraph } from '@tiptap/extension-paragraph'
import { Text } from '@tiptap/extension-text'
import { CodeBlock } from '@tiptap/extension-code-block'
import { MarkdownManager } from '@tiptap/markdown'
import { describe, expect, it } from 'vitest'

const createMarkdownManager = () => {
  const markdownManager = new MarkdownManager()
  markdownManager.registerExtension(Document)
  markdownManager.registerExtension(Paragraph)
  markdownManager.registerExtension(Text)
  markdownManager.registerExtension(CodeBlock)

  return markdownManager
}

describe('Markdown tilde-fenced code blocks', () => {
  it('parses tilde-fenced code blocks with language and preserves content', () => {
    const markdownManager = createMarkdownManager()
    const markdown = "~~~python\nprint('~~~')\n~~~"

    const doc = markdownManager.parse(markdown)
    const codeBlock = doc.content?.[0]

    expect(codeBlock?.type).toBe('codeBlock')
    expect(codeBlock?.attrs?.language).toBe('python')
    expect(codeBlock?.content?.[0]?.text).toBe("print('~~~')")
  })

  it('parses longer tilde fences with multi-line content', () => {
    const markdownManager = createMarkdownManager()
    const markdown = '~~~~\nalpha\nbeta\n~~~~'

    const doc = markdownManager.parse(markdown)
    const codeBlock = doc.content?.[0]

    expect(codeBlock?.type).toBe('codeBlock')
    expect(codeBlock?.attrs?.language).toBe(null)
    expect(codeBlock?.content?.[0]?.text).toBe('alpha\nbeta')
  })

  it('produces identical results for tilde and backtick fences', () => {
    const markdownManager = createMarkdownManager()
    const tildeMarkdown = '~~~\nvalue 1\nvalue 2\n~~~'
    const backtickMarkdown = '```\nvalue 1\nvalue 2\n```'

    const tildeDoc = markdownManager.parse(tildeMarkdown)
    const backtickDoc = markdownManager.parse(backtickMarkdown)

    expect(tildeDoc).toEqual(backtickDoc)
    expect(tildeDoc.content?.[0]?.type).toBe('codeBlock')
  })

  it('still parses indented code blocks', () => {
    const markdownManager = createMarkdownManager()
    const markdown = '    indented line 1\n    indented line 2'

    const doc = markdownManager.parse(markdown)
    const codeBlock = doc.content?.[0]

    expect(codeBlock?.type).toBe('codeBlock')
    expect(codeBlock?.attrs?.language).toBe(null)
    expect(codeBlock?.content?.[0]?.text).toBe('indented line 1\nindented line 2')
  })
})
