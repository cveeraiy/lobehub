import path from 'node:path';

import { defineConfig, loadEnv } from 'vite';

import { viteMarkdownImport } from './plugins/vite/markdownImport';

const mode = process.env.NODE_ENV === 'production' ? 'production' : 'development';
Object.assign(process.env, loadEnv(mode, process.cwd(), ''));

export default defineConfig({
  build: {
    // Output a single CJS bundle for Node.js
    outDir: 'dist/hono-server',
    ssr: true,
    target: 'node20',
    rollupOptions: {
      input: path.resolve(__dirname, 'src/hono-server/index.ts'),
      output: {
        entryFileNames: 'server.mjs',
        format: 'esm',
        // Single chunk — avoids cross-chunk init_* issues with rolldown
        inlineDynamicImports: true,
      },
      // Externalize optional native modules that may not be installed
      external: [
        'zlib-sync', // optional dep of @discordjs/ws
        'bufferutil', // optional dep of ws
        'utf-8-validate', // optional dep of ws
        'erlpack', // optional dep of discord.js
      ],
    },
    // Don't minify for debugging; enable in production later
    minify: false,
    sourcemap: true,
  },

  resolve: {
    alias: {
      // Browser polyfills → Node builtins
      'path-browserify-esm': 'path',
    },
    tsconfigPaths: true,
  },

  plugins: [
    // Handle `import content from './AGENTS.md'` etc.
    viteMarkdownImport(),
  ],

  // Mark heavy Node.js deps as external (not bundled)
  // These must be available at runtime via node_modules
  ssr: {
    external: [
      // Core runtime deps
      '@hono/node-server',
      'hono',
      'drizzle-orm',
      'postgres',
      // Auth
      'better-auth',
      // Upstash
      '@upstash/qstash',
      '@upstash/workflow',
      // Heavy vendor SDKs — no need to bundle
      '@aws-sdk',
      '@azure',
      '@google-cloud',
      'openai',
      'ioredis',
      // Native Node addons (binary .node files can't be bundled)
      '@napi-rs/canvas',
      '@napi-rs/canvas-darwin-arm64',
      '@napi-rs/canvas-darwin-x64',
      '@napi-rs/canvas-linux-x64-gnu',
      '@napi-rs/canvas-linux-x64-musl',
      '@napi-rs/canvas-linux-arm64-gnu',
      '@napi-rs/canvas-linux-arm64-musl',
      '@napi-rs/canvas-win32-x64-msvc',
      'sharp',
    ],
    // Bundle everything else (resolves ESM-only packages, broken exports, etc.)
    noExternal: true,
  },
});
