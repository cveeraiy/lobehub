import { BRANDING_NAME, ORG_NAME } from '@lobechat/business-const';
import { OG_URL } from '@lobechat/const';
import { type Context, Hono } from 'hono';

import { getServerFeatureFlagsValue, type IFeatureFlags } from '@/config/featureFlags';
import { OFFICIAL_URL } from '@/const/url';
import { isCustomORG } from '@/const/version';
import { analyticsEnv } from '@/envs/analytics';
import { appEnv } from '@/envs/app';
import { fileEnv } from '@/envs/file';
import { pythonEnv } from '@/envs/python';
import { getServerGlobalConfig } from '@/server/globalConfig';
import { translation } from '@/server/translation';
import { serializeForHtml } from '@/server/utils/serializeForHtml';
import {
  type AnalyticsConfig,
  type SPAClientEnv,
  type SPAServerConfig,
} from '@/types/spaServerConfig';

const spaApp = new Hono();

const isDev = process.env.NODE_ENV === 'development';
const VITE_DEV_ORIGIN = 'http://localhost:9876';

// ============ Cached config (computed once at startup) ============ //
let cachedAnalyticsConfig: AnalyticsConfig | undefined;
let cachedClientEnv: SPAClientEnv | undefined;
let cachedFeatureFlags: Partial<IFeatureFlags> | undefined;
let cachedServerConfig: Awaited<ReturnType<typeof getServerGlobalConfig>> | undefined;
let cachedDesktopTemplate: string | undefined;
let cachedMobileTemplate: string | undefined;
const seoMetaCache = new Map<string, string>();

async function rewriteViteAssetUrls(html: string): Promise<string> {
  const { parseHTML } = await import('linkedom');
  const { document } = parseHTML(html);

  document.querySelectorAll('script[src]').forEach((el: Element) => {
    const src = el.getAttribute('src');
    if (src && src.startsWith('/')) {
      el.setAttribute('src', `${VITE_DEV_ORIGIN}${src}`);
    }
  });

  document.querySelectorAll('link[href]').forEach((el: Element) => {
    const href = el.getAttribute('href');
    if (href && href.startsWith('/')) {
      el.setAttribute('href', `${VITE_DEV_ORIGIN}${href}`);
    }
  });

  document.querySelectorAll('script[type="module"]:not([src])').forEach((el: Element) => {
    const text = el.textContent || '';
    if (text.includes('/@')) {
      el.textContent = text.replaceAll(
        /from\s+["'](\/[@\w].*?)["']/g,
        (_match: string, p: string) => `from "${VITE_DEV_ORIGIN}${p}"`,
      );
    }
  });

  const workerPatch = document.createElement('script');
  workerPatch.textContent = `(function(){
var O=globalThis.Worker;
globalThis.Worker=function(u,o){
var h=typeof u==='string'?u:u instanceof URL?u.href:'';
if(h.startsWith('${VITE_DEV_ORIGIN}')){
var b=new Blob(['import "'+h+'";'],{type:'application/javascript'});
return new O(URL.createObjectURL(b),Object.assign({},o,{type:'module'}));
}return new O(u,o)};
globalThis.Worker.prototype=O.prototype;
})();`;
  const head = document.querySelector('head');
  if (head?.firstChild) {
    head.insertBefore(workerPatch, head.firstChild);
  }

  return document.toString();
}

async function getTemplate(isMobile: boolean): Promise<string> {
  if (isDev) {
    try {
      const res = await fetch(VITE_DEV_ORIGIN);
      const html = await res.text();
      return rewriteViteAssetUrls(html);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[SPA] Failed to fetch dev template from ${VITE_DEV_ORIGIN}: ${msg}`);
      return `<!DOCTYPE html><html><body style="font-family:monospace;padding:2rem">
        <h1>Vite dev server not reachable</h1>
        <p>Ensure <code>bun run dev:spa</code> is running on port 9876.</p>
        <pre>${msg}</pre></body></html>`;
    }
  }

  // In production, return cached templates (read once at startup)
  if (isMobile && cachedMobileTemplate) return cachedMobileTemplate;
  if (!isMobile && cachedDesktopTemplate) return cachedDesktopTemplate;

  const { readFileSync, existsSync } = await import('node:fs');
  const { resolve } = await import('node:path');

  cachedDesktopTemplate = readFileSync(resolve('dist/desktop/index.html'), 'utf8');

  const mobileHtmlPath = resolve('dist/mobile/index.mobile.html');
  const mobileHtmlFallback = resolve('dist/mobile/index.html');
  cachedMobileTemplate = readFileSync(
    existsSync(mobileHtmlPath) ? mobileHtmlPath : mobileHtmlFallback,
    'utf8',
  );

  return isMobile ? cachedMobileTemplate : cachedDesktopTemplate;
}

function buildAnalyticsConfig(): AnalyticsConfig {
  const config: AnalyticsConfig = {};

  if (analyticsEnv.ENABLE_GOOGLE_ANALYTICS && analyticsEnv.GOOGLE_ANALYTICS_MEASUREMENT_ID) {
    config.google = { measurementId: analyticsEnv.GOOGLE_ANALYTICS_MEASUREMENT_ID };
  }

  if (analyticsEnv.ENABLED_PLAUSIBLE_ANALYTICS && analyticsEnv.PLAUSIBLE_DOMAIN) {
    config.plausible = {
      domain: analyticsEnv.PLAUSIBLE_DOMAIN,
      scriptBaseUrl: analyticsEnv.PLAUSIBLE_SCRIPT_BASE_URL,
    };
  }

  if (analyticsEnv.ENABLED_UMAMI_ANALYTICS && analyticsEnv.UMAMI_WEBSITE_ID) {
    config.umami = {
      scriptUrl: analyticsEnv.UMAMI_SCRIPT_URL,
      websiteId: analyticsEnv.UMAMI_WEBSITE_ID,
    };
  }

  if (analyticsEnv.ENABLED_CLARITY_ANALYTICS && analyticsEnv.CLARITY_PROJECT_ID) {
    config.clarity = { projectId: analyticsEnv.CLARITY_PROJECT_ID };
  }

  if (analyticsEnv.ENABLED_POSTHOG_ANALYTICS && analyticsEnv.POSTHOG_KEY) {
    config.posthog = {
      debug: analyticsEnv.DEBUG_POSTHOG_ANALYTICS,
      host: analyticsEnv.POSTHOG_HOST,
      key: analyticsEnv.POSTHOG_KEY,
    };
  }

  if (analyticsEnv.ENABLED_X_ADS && analyticsEnv.X_ADS_PIXEL_ID) {
    config.xAds = {
      eventIds: {
        login_or_signup_clicked: analyticsEnv.X_ADS_LOGIN_OR_SIGNUP_CLICKED_EVENT_ID,
        main_page_view: analyticsEnv.X_ADS_MAIN_PAGE_VIEW_EVENT_ID,
      },
      pixelId: analyticsEnv.X_ADS_PIXEL_ID,
      purchaseEventId: analyticsEnv.X_ADS_PURCHASE_EVENT_ID,
    };
  }

  if (analyticsEnv.REACT_SCAN_MONITOR_API_KEY) {
    config.reactScan = { apiKey: analyticsEnv.REACT_SCAN_MONITOR_API_KEY };
  }

  if (
    process.env.NEXT_PUBLIC_DESKTOP_PROJECT_ID &&
    process.env.NEXT_PUBLIC_DESKTOP_UMAMI_BASE_URL
  ) {
    config.desktop = {
      baseUrl: process.env.NEXT_PUBLIC_DESKTOP_UMAMI_BASE_URL,
      projectId: process.env.NEXT_PUBLIC_DESKTOP_PROJECT_ID,
    };
  }

  return config;
}

function buildClientEnv(): SPAClientEnv {
  return {
    marketBaseUrl: appEnv.MARKET_BASE_URL,
    pyodideIndexUrl: pythonEnv.NEXT_PUBLIC_PYODIDE_INDEX_URL,
    pyodidePipIndexUrl: pythonEnv.NEXT_PUBLIC_PYODIDE_PIP_INDEX_URL,
    s3FilePath: fileEnv.NEXT_PUBLIC_S3_FILE_PATH,
  };
}

async function buildSeoMeta(locale: string): Promise<string> {
  const { t } = await translation('metadata', locale);
  const title = t('chat.title', { appName: BRANDING_NAME });
  const description = t('chat.description', { appName: BRANDING_NAME });

  return [
    `<title>${title}</title>`,
    `<meta name="description" content="${description}" />`,
    `<meta property="og:title" content="${title}" />`,
    `<meta property="og:description" content="${description}" />`,
    `<meta property="og:type" content="website" />`,
    `<meta property="og:url" content="${OFFICIAL_URL}" />`,
    `<meta property="og:image" content="${OG_URL}" />`,
    `<meta property="og:site_name" content="${BRANDING_NAME}" />`,
    `<meta property="og:locale" content="${locale}" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${title}" />`,
    `<meta name="twitter:description" content="${description}" />`,
    `<meta name="twitter:image" content="${OG_URL}" />`,
    `<meta name="twitter:site" content="${isCustomORG ? `@${ORG_NAME}` : '@lobehub'}" />`,
  ].join('\n    ');
}

function detectIsMobile(userAgent: string | undefined): boolean {
  if (!userAgent) return false;
  return /Mobile|Android|iPhone|iPad|iPod|webOS|BlackBerry|Opera Mini|IEMobile/i.test(userAgent);
}

const SUPPORTED_LOCALES = [
  'ar',
  'bg-BG',
  'de-DE',
  'en-US',
  'es-ES',
  'fa-IR',
  'fr-FR',
  'it-IT',
  'ja-JP',
  'ko-KR',
  'nl-NL',
  'pl-PL',
  'pt-BR',
  'ru-RU',
  'tr-TR',
  'vi-VN',
  'zh-CN',
  'zh-TW',
];

function detectLocale(acceptLanguage: string | undefined): string {
  if (!acceptLanguage) return 'en-US';
  const tags = acceptLanguage
    .split(',')
    .map((t) => t.split(';')[0]?.trim())
    .filter(Boolean);

  for (const tag of tags) {
    // Exact match
    if (SUPPORTED_LOCALES.includes(tag)) return tag;
    // Language-only match (e.g. 'zh' -> 'zh-CN', 'ja' -> 'ja-JP')
    const lang = tag.split('-')[0];
    const match = SUPPORTED_LOCALES.find((l) => l.startsWith(lang));
    if (match) return match;
  }
  return 'en-US';
}

// Shared SPA handler — serves the SPA HTML template with injected server config.
async function serveSPA(c: Context) {
  const userAgent = c.req.header('user-agent');
  const acceptLanguage = c.req.header('accept-language');
  const isMobile = detectIsMobile(userAgent);
  const locale = detectLocale(acceptLanguage);

  // Use cached values (env-derived, don't change at runtime)
  if (!cachedAnalyticsConfig) cachedAnalyticsConfig = buildAnalyticsConfig();
  if (!cachedClientEnv) cachedClientEnv = buildClientEnv();
  if (!cachedFeatureFlags) cachedFeatureFlags = getServerFeatureFlagsValue();

  if (!cachedServerConfig) cachedServerConfig = await getServerGlobalConfig();

  const spaConfig: SPAServerConfig = {
    analyticsConfig: cachedAnalyticsConfig,
    clientEnv: cachedClientEnv,
    config: cachedServerConfig,
    featureFlags: cachedFeatureFlags,
    isMobile,
  };

  let html = await getTemplate(isMobile);

  html = html.replace(
    /window\.__SERVER_CONFIG__\s*=\s*undefined;\s*\/\*\s*SERVER_CONFIG\s*\*\//,
    `window.__SERVER_CONFIG__ = ${serializeForHtml(spaConfig)};`,
  );

  let seoMeta = seoMetaCache.get(locale);
  if (!seoMeta) {
    seoMeta = await buildSeoMeta(locale);
    seoMetaCache.set(locale, seoMeta);
  }
  html = html.replace('<!--SEO_META-->', seoMeta);
  html = html.replace('<!--ANALYTICS_SCRIPTS-->', '');

  return c.html(html, 200, {
    'Cache-Control': 'no-cache',
  });
}

// Catch-all: serve SPA for any unmatched GET request (client-side routing).
// This covers all SPA paths including /spa/*, auth pages (/signin, /signup, etc.),
// and any other client-side routes handled by react-router-dom.
spaApp.get('*', serveSPA);

export default spaApp;
