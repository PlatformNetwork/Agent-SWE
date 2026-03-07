import { describe, it, expect } from 'vitest'
import { deflateSync } from 'node:zlib'
import { createHash } from 'node:crypto'
import git from '@ashishkumar472/cf-git'
import { GitCloneService } from './git-clone-service'
import { GitReceivePackService } from './git-receive-pack-service'
import { MemFS } from './memfs'

const nullChar = String.fromCharCode(0)
const newlineChar = String.fromCharCode(10)
function buildPushRequest(
  refs: Array<{ oldOid: string; newOid: string; refName: string }>,
  packfileBytes: Uint8Array
): Uint8Array {
  const encoder = new TextEncoder()
  const chunks: Uint8Array[] = []

  for (let i = 0; i < refs.length; i += 1) {
    const { oldOid, newOid, refName } = refs[i]
    let line = oldOid + ' ' + newOid + ' ' + refName
    if (i === 0) {
      line += nullChar + ' report-status'
    }
    line += newlineChar
    const lengthHex = (line.length + 4).toString(16).padStart(4, '0')
    chunks.push(encoder.encode(lengthHex + line))
  }

  chunks.push(encoder.encode('0000'))
  chunks.push(packfileBytes)

  const totalLength = chunks.reduce((sum, c) => sum + c.length, 0)
  const result = new Uint8Array(totalLength)
  let offset = 0
  for (const chunk of chunks) {
    result.set(chunk, offset)
    offset += chunk.length
  }
  return result
}

const zeroOid = '0'.repeat(40)
function buildValidPackfile(blobContent: string): { packBytes: Uint8Array; blobOid: string } {
  const content = Buffer.from(blobContent)
  const gitObjectHeader = Buffer.concat([Buffer.from('blob ' + String(content.length)), Buffer.from([0])])
  const blobOid = createHash('sha1')
    .update(Buffer.concat([gitObjectHeader, content]))
    .digest('hex')

  const header = Buffer.alloc(12)
  header.write('PACK', 0)
  header.writeUInt32BE(2, 4)
  header.writeUInt32BE(1, 8)

  if (content.length > 15) {
    throw new Error('buildValidPackfile: content too long for simple header')
  }
  const objHeader = Buffer.from([(3 << 4) | content.length])

  const deflated = deflateSync(content)
  const packBody = Buffer.concat([header, objHeader, deflated])
  const checksum = createHash('sha1').update(packBody).digest()
  const packBytes = new Uint8Array(Buffer.concat([packBody, checksum]))

  return { packBytes, blobOid }
}

async function pushToRepo(
  fs: MemFS,
  refs: Array<{ oldOid: string; newOid: string; refName: string }>,
  packBytes: Uint8Array
): Promise<void> {
  const requestData = buildPushRequest(refs, packBytes)
  const { result } = await GitReceivePackService.handleReceivePack(fs, requestData)
  if (!result.success) {
    throw new Error('Push failed: ' + result.errors.join(', '))
  }
}
function parseInfoRefsLines(response: string): string[] {
  const encoder = new TextEncoder()
  const bytes = encoder.encode(response)
  const decoder = new TextDecoder()
  const lines: string[] = []
  let offset = 0

  while (offset + 4 <= bytes.length) {
    const lengthHex = decoder.decode(bytes.slice(offset, offset + 4))
    const length = parseInt(lengthHex, 16)
    offset += 4
    if (!length) {
      continue
    }
    const payloadLength = length - 4
    const end = offset + payloadLength
    if (end > bytes.length || payloadLength < 0) {
      break
    }
    const payload = decoder.decode(bytes.slice(offset, end))
    lines.push(payload)
    offset = end
  }

  return lines
}

describe('Git info/refs symref advertisement', () => {
  it('includes symref=HEAD:<branch> in upload-pack capabilities for clone', async () => {
    const fs = new MemFS()

    const { packBytes, blobOid } = buildValidPackfile('clone-default')
    await pushToRepo(
      fs,
      [{ oldOid: zeroOid, newOid: blobOid, refName: 'refs/heads/main' }],
      packBytes
    )

    const response = await GitCloneService.handleInfoRefs(fs)
    const lines = parseInfoRefsLines(response)
    const headLine = lines.find(line => line.indexOf(' HEAD') >= 0)

    expect(headLine).toBeTruthy()
    expect(headLine).toContain('symref=HEAD:refs/heads/main')
    expect(headLine).toContain('agent=git/isomorphic-git')
  })

  it('includes symref=HEAD:<branch> in receive-pack capabilities for push', async () => {
    const fs = new MemFS()

    const { packBytes, blobOid } = buildValidPackfile('push-default')
    await pushToRepo(
      fs,
      [{ oldOid: zeroOid, newOid: blobOid, refName: 'refs/heads/main' }],
      packBytes
    )

    const response = await GitReceivePackService.handleInfoRefs(fs)
    const lines = parseInfoRefsLines(response)
    const headLine = lines.find(line => line.indexOf(' HEAD') >= 0)

    expect(headLine).toBeTruthy()
    expect(headLine).toContain('symref=HEAD:refs/heads/main')
    expect(headLine).toContain('report-status')
  })
})

describe('Git pkt-line length formatting', () => {
  it('uses UTF-8 byte length for upload-pack pkt-line headers', async () => {
    const fs = new MemFS()
    const { packBytes, blobOid } = buildValidPackfile('emoji-clone')

    await pushToRepo(
      fs,
      [{ oldOid: zeroOid, newOid: blobOid, refName: 'refs/heads/main' }],
      packBytes
    )

    await git.writeRef({ fs, dir: '/', ref: 'refs/heads/feature-✨', value: blobOid, force: true })

    const response = await GitCloneService.handleInfoRefs(fs)
    const lines = parseInfoRefsLines(response)
    const featureLine = lines.find(line => line.indexOf('refs/heads/feature-✨') >= 0)

    expect(response.indexOf('refs/heads/feature-✨') >= 0).toBe(true)
    expect(featureLine).toBeTruthy()

    const lineWithoutPrefix = featureLine || ''
    const headerIndex = response.indexOf(lineWithoutPrefix) - 4
    const lengthHex = response.slice(headerIndex, headerIndex + 4)
    const length = parseInt(lengthHex, 16)
    const utf8Length = new TextEncoder().encode(lineWithoutPrefix).length + 4

    expect(length).toBe(utf8Length)
  })
})
