import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import type { PluginOption, ViteDevServer } from 'vite';
import { defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

import { viteEnvRestartKeys } from './plugins/vite/envRestartKeys';
import {
  createSharedRolldownOutput,
  sharedOptimizeDeps,
  sharedRendererDefine,
  sharedRendererPlugins,
} from './plugins/vite/sharedRendererConfig';
import { vercelSkewProtection } from './plugins/vite/vercelSkewProtection';

const isMobile = process.env.MOBILE === 'true';
const mode = process.env.NODE_ENV === 'production' ? 'production' : 'development';

Object.assign(process.env, loadEnv(mode, process.cwd(), ''));

const isDev = process.env.NODE_ENV !== 'production';
const platform = isMobile ? 'mobile' : 'web';

const resolveCommandExecutable = (cmd: string) => {
  const pathValue = process.env.PATH;
  if (!pathValue) return;

  if (process.platform === 'win32') {
    const pathExt = (process.env.PATHEXT || '.COM;.EXE;.BAT;.CMD')
      .split(';')
      .filter(Boolean)
      .map((ext) => ext.toLowerCase());
    const candidateNames = cmd.includes('.') ? [cmd] : pathExt.map((ext) => `${cmd}${ext}`);

    for (const entry of pathValue.split(path.delimiter).filter(Boolean)) {
      for (const candidate of candidateNames) {
        const resolved = path.win32.join(entry, candidate);
        if (fs.existsSync(resolved)) return resolved;
      }
    }

    return;
  }

  for (const entry of pathValue.split(path.delimiter).filter(Boolean)) {
    const resolved = path.join(entry, cmd);
    if (fs.existsSync(resolved)) return resolved;
  }
};

const openExternalBrowser = async (
  url: string,
  logger?: { warn: (msg: string) => void },
): Promise<boolean> => {
  const command =
    process.platform === 'win32'
      ? {
          args: ['url.dll,FileProtocolHandler', url],
          cmd: 'rundll32',
        }
      : {
          args: [url],
          cmd: process.platform === 'darwin' ? 'open' : 'xdg-open',
        };

  const executable = resolveCommandExecutable(command.cmd);
  if (!executable) {
    logger?.warn(`openExternalBrowser: ${command.cmd} not found on PATH`);
    return false;
  }

  return new Promise<boolean>((resolve) => {
    try {
      const child = spawn(executable, command.args, {
        detached: true,
        stdio: 'ignore',
      });
      let settled = false;
      const done = (ok: boolean, reason?: string) => {
        if (settled) return;
        settled = true;
        if (!ok && reason) logger?.warn(`openExternalBrowser: ${reason}`);
        resolve(ok);
      };
      child.once('error', (err) => done(false, (err as Error).message));
      child.once('spawn', () => {
        child.unref();
        done(true);
      });
      setTimeout(() => done(true), 200);
    } catch (e) {
      logger?.warn(`openExternalBrowser: ${(e as Error).message}`);
      resolve(false);
    }
  });
};

export default defineConfig({
  base: isDev ? '/' : process.env.VITE_CDN_BASE || '/_spa/',
  build: {
    outDir: isMobile ? 'dist/mobile' : 'dist/web',
    reportCompressedSize: false,
    rolldownOptions: {
      input: path.resolve(__dirname, isMobile ? 'index.mobile.html' : 'index.html'),
      output: createSharedRolldownOutput({ strictExecutionOrder: true }),
    },
  },
  define: sharedRendererDefine({ isMobile }),
  experimental: {
    bundledDev: false,
  },
  resolve: {
    alias: (() => {
      // Resolve the real (non-symlink) path so rolldown matches it regardless
      // of which symlink path a workspace package resolves @lobehub/ui through.
      const uiRoot = fs.realpathSync(path.resolve(__dirname, 'node_modules/@lobehub/ui'));
      return ['awesome', 'base-ui', 'brand', 'chat', 'icons', 'mdx', 'mobile'].map((sub) => ({
        find: `@lobehub/ui/${sub}`,
        replacement: path.join(uiRoot, `es/${sub}/index.mjs`),
      }));
    })(),
    tsconfigPaths: true,
  },
  optimizeDeps: sharedOptimizeDeps,
  plugins: [
    vercelSkewProtection(),
    viteEnvRestartKeys(['APP_URL']),
    ...sharedRendererPlugins({ platform }),

    isDev && {
      name: 'lobe-dev-proxy-print',
      configureServer(server: ViteDevServer) {
        const ONLINE_HOST = 'https://app.lobehub.com';
        const c = {
          green: (s: string) => `\x1B[32m${s}\x1B[0m`,
          bold: (s: string) => `\x1B[1m${s}\x1B[0m`,
          cyan: (s: string) => `\x1B[36m${s}\x1B[0m`,
        };
        const { info } = server.config.logger;
        const isBundledDev = (server.config.experimental as any)?.bundledDev;

        const getProxyUrl = () => {
          const urls = server.resolvedUrls;
          if (!urls?.local?.[0]) return;
          const localHost = urls.local[0].replace(/\/$/, '');
          return `${ONLINE_HOST}/_dangerous_local_dev_proxy?debug-host=${encodeURIComponent(localHost)}`;
        };
        const printProxyUrl = () => {
          const proxyUrl = getProxyUrl();
          if (!proxyUrl) return;
          const colorUrl = (url: string) =>
            c.cyan(url.replace(/:(\d+)\//, (_, port) => `:${c.bold(port)}/`));
          info(`  ${c.green('➜')}  ${c.bold('Debug Proxy')}: ${colorUrl(proxyUrl)}`);
        };
        const openProxyUrl = async () => {
          const proxyUrl = getProxyUrl();
          if (!proxyUrl) return;

          const opened = await openExternalBrowser(proxyUrl, server.config.logger);

          if (!opened) {
            server.config.logger.warn(`Failed to open Debug Proxy automatically: ${proxyUrl}`);
          }
        };

        if (isBundledDev) {
          // Disable Vite's built-in browser opening. We always open the debug
          // proxy URL after the first bundled compile finishes instead.
          server.openBrowser = () => {};

          const spinnerFrames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
          let spinnerIdx = 0;
          let spinnerTimer: NodeJS.Timeout | null = null;
          const formatElapsed = (ms: number) =>
            ms < 1000 ? `${Math.max(0, Math.round(ms))}ms` : `${(ms / 1000).toFixed(1)}s`;

          const startSpinner = (msg: string, since: number) => {
            spinnerIdx = 0;
            spinnerTimer = setInterval(() => {
              const elapsed = formatElapsed(Date.now() - since);
              process.stdout.write(`\r${c.cyan(spinnerFrames[spinnerIdx])} ${msg} (${elapsed})`);
              spinnerIdx = (spinnerIdx + 1) % spinnerFrames.length;
            }, 80);
          };
          const stopSpinner = (clearLine = true) => {
            if (spinnerTimer) {
              clearInterval(spinnerTimer);
              spinnerTimer = null;
            }
            if (clearLine) process.stdout.write('\r\x1B[K');
          };

          server.httpServer?.once('listening', () => {
            void (async () => {
              const rootUrl =
                server.resolvedUrls?.local?.[0] ||
                `http://localhost:${String(server.config.server.port || 9876)}/`;
              const startedAt = Date.now();
              const timeout = 180_000;
              const interval = 400;
              let ready = false;

              startSpinner('Vite: compile and bundle...', startedAt);

              try {
                while (Date.now() - startedAt < timeout) {
                  try {
                    const res = await fetch(rootUrl, { signal: AbortSignal.timeout(5_000) });
                    const text = await res.text();
                    if (text.includes('Bundling in progress')) {
                      await new Promise((r) => setTimeout(r, interval));
                      continue;
                    }
                    ready = true;
                    stopSpinner();
                    info(
                      `  ${c.green('✅')}  Vite: compile and bundle finished (${res.status}) ${rootUrl}`,
                    );
                    // void openProxyUrl();
                    break;
                  } catch {
                    await new Promise((r) => setTimeout(r, interval));
                  }
                }
              } catch (e) {
                stopSpinner();
                console.warn('⚠️ Vite: could not wait for compile and bundle:', e);
              }

              if (!ready && spinnerTimer) {
                stopSpinner();
                console.warn(`⚠️ Vite: compile and bundle timed out after ${timeout / 1000}s`);
              }

              printProxyUrl();
            })();
          });
        }

        return () => {
          server.printUrls = () => {
            if (isBundledDev) return;
            printProxyUrl();
          };
        };
      },
    },

    VitePWA({
      injectRegister: null,
      manifest: false,
      registerType: 'prompt',
      workbox: {
        globPatterns: ['**/*.{js,css,html,woff2}'],
        maximumFileSizeToCacheInBytes: 10 * 1024 * 1024,
        runtimeCaching: [
          {
            handler: 'StaleWhileRevalidate',
            options: { cacheName: 'google-fonts-stylesheets' },
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
          },
          {
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-webfonts',
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 365, maxEntries: 30 },
            },
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
          },
          {
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'image-assets',
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 30, maxEntries: 100 },
            },
            urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp|ico|avif)$/i,
          },
          {
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: { maxAgeSeconds: 60 * 5, maxEntries: 50 },
            },
            urlPattern: /\/(api|webapi)\/.*/i,
          },
        ],
      },
    }),
  ].filter(Boolean) as PluginOption[],

  server: {
    cors: true,
    host: true,
    port: 9876,
    proxy: {
      '/api': `http://localhost:${process.env.PORT || 8000}`,
      '/f': `http://localhost:${process.env.PORT || 8000}`,
      '/oidc/clear-session': `http://localhost:${process.env.PORT || 8000}`,
      '/webapi': `http://localhost:${process.env.PORT || 8000}`,
    },
    warmup: {
      clientFiles: [
        // Entry point & SPA bootstrap (critical path)
        './src/initialize.ts',
        './src/spa/**/*.tsx',
        './src/utils/router.tsx',

        // Root layout & providers (synchronous imports of main layout)
        './src/layout/**/*.{ts,tsx}',
        './src/routes/(main)/_layout/**/*.{ts,tsx}',
        './src/routes/(main)/home/**/*.{ts,tsx}',

        // Components used by the root layout shell
        './src/components/Loading/**/*.{ts,tsx}',
        './src/components/Error/**/*.{ts,tsx}',
        './src/features/NavPanel/**/*.{ts,tsx}',
        './src/features/AlertBanner/**/*.{ts,tsx}',
        './src/features/HotkeyHelperPanel/**/*.{ts,tsx}',
        './src/features/CommandMenu/**/*.{ts,tsx}',

        // Stores used during initial render
        './src/store/global/**/*.{ts,tsx}',
        './src/store/serverConfig/**/*.{ts,tsx}',
        './src/store/user/**/*.{ts,tsx}',

        // Shared infrastructure needed early
        './src/config/**/*.ts',
        './src/const/**/*.ts',
        './src/envs/**/*.ts',
        './src/styles/**/*.ts',
        './src/locales/**/*.ts',
        './src/business/**/*.{ts,tsx}',

        // Monorepo packages used client-side at init
        './packages/const/src/**/*.ts',
        './packages/types/src/**/*.ts',
        './packages/utils/src/**/*.ts',
      ],
    },
  },
});
