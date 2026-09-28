/// <reference types="vitest/config" />
// Vite config for the console. No React plugin: esbuild's automatic JSX runtime is enough (no fast
// refresh, no Babel in the toolchain). Build output is strict-CSP friendly: no inline scripts or
// styles, no data: fonts (assetsInlineLimit 0), no module-preload polyfill.
import { defineConfig } from 'vite';
import { consoleConfig, connectOrigins, globalHeaders } from './security-headers.mjs';

const config = consoleConfig();
const headers = globalHeaders({ connect: connectOrigins(config) });
// Local http dev/preview: HSTS and upgrade-insecure-requests make no sense on loopback.
delete (headers as Record<string, string>)['Strict-Transport-Security'];
headers['Content-Security-Policy'] = headers['Content-Security-Policy'].replace(
  '; upgrade-insecure-requests',
  '',
);

export default defineConfig({
  define: {
    __NF_CONSOLE_CONFIG__: JSON.stringify(config),
  },
  esbuild: {
    jsx: 'automatic',
    legalComments: 'none',
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    assetsInlineLimit: 0,
    modulePreload: { polyfill: false },
    reportCompressedSize: true,
  },
  preview: { headers, port: 4173, strictPort: true },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['./src/test/setup.ts'],
    // RAM is tight on the dev PC: one worker process.
    pool: 'forks',
    poolOptions: { forks: { singleFork: true } },
    css: false,
    testTimeout: 15_000,
  },
});
