import { readFile, writeFile } from 'node:fs/promises'

const reportPath = new URL('../coverage/lcov.info', import.meta.url)
const lcov = await readFile(reportPath, 'utf8')
const normalized = lcov.replace(/^SF:(?!frontend\/)(.+)$/gm, (_line, sourcePath) => {
  const posixPath = sourcePath.replaceAll('\\', '/')
  if (!posixPath.startsWith('src/')) {
    throw new Error(`Unexpected LCOV source path: ${sourcePath}`)
  }
  return `SF:frontend/${posixPath}`
})

await writeFile(reportPath, normalized)
