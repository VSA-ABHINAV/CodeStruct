import { defineConfig } from 'vitest/config'
import { applicationVersion } from './version.config.js'

export default defineConfig({
  define: {
    __CODESTRUCT_VERSION__: JSON.stringify(applicationVersion),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['src/**/*.test.js', 'src/**/*.test.jsx'],
    setupFiles: ['./src/test/setup.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: 'coverage',
      include: [
        'src/App.jsx',
        'src/Graph.jsx',
        'src/api/**/*.js',
        'src/features/architecture/**/*.{js,jsx}',
      ],
      exclude: ['src/**/*.test.*', 'src/**/fixtures/**'],
      thresholds: {
        statements: 70,
        branches: 60,
        functions: 65,
        lines: 75,
      },
    },
  },
})
