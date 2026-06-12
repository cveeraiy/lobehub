import '../initialize';

import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';

import BootErrorBoundary from '@/components/BootErrorBoundary';
import { createAppRouter } from '@/utils/router';

import { webRoutes } from './router/webRouter.config';

const debugProxyBase = '/_dangerous_local_dev_proxy';
const basename =
  window.__DEBUG_PROXY__ || window.location.pathname.startsWith(debugProxyBase)
    ? debugProxyBase
    : undefined;

const router = createAppRouter(webRoutes, { basename });

createRoot(document.getElementById('root')!).render(
  <BootErrorBoundary>
    <RouterProvider router={router} />
  </BootErrorBoundary>,
);
