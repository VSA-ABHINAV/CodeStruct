import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const about = readFileSync(
  fileURLToPath(new URL('../backend/src/codestruct/__about__.py', import.meta.url)),
  'utf8',
)

export const applicationVersion = about.match(
  /__version__\s*=\s*["']([^"']+)["']/,
)?.[1]

if (!applicationVersion) throw new Error('CodeStruct version metadata is missing')
