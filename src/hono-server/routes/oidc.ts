import { Hono } from 'hono';

import {
  DELETE as oidcDelete,
  GET as oidcGet,
  PATCH as oidcPatch,
  POST as oidcPost,
  PUT as oidcPut,
} from '@/handlers/oidc/[...oidc]/route';
import { GET as desktopCallback } from '@/handlers/oidc/callback/desktop/route';
import { POST as clearSession } from '@/handlers/oidc/clear-session/route';
import { POST as consent } from '@/handlers/oidc/consent/route';
import { GET as handoff } from '@/handlers/oidc/handoff/route';
import { GET as interactionDetails } from '@/handlers/oidc/interaction/route';

const oidc = new Hono();

// ============ OIDC Provider Catch-All ============ //
// The [...oidc] catch-all handles all OIDC provider interactions
oidc.get('/oidc/*', (c) => oidcGet(c.req.raw));
oidc.post('/oidc/*', (c) => oidcPost(c.req.raw));
oidc.put('/oidc/*', (c) => oidcPut(c.req.raw));
oidc.delete('/oidc/*', (c) => oidcDelete(c.req.raw));
oidc.patch('/oidc/*', (c) => oidcPatch(c.req.raw));

// ============ OIDC Specific Routes ============ //
// These must be registered before the catch-all to take priority,
// but Hono matches by registration order within the same path pattern.
// Since these are more specific paths, register them on a separate sub-app.

const oidcSpecific = new Hono();

oidcSpecific.get('/oidc/callback/desktop', (c) => desktopCallback(c.req.raw) as any);
oidcSpecific.post('/oidc/clear-session', (c) => clearSession(c.req.raw) as any);
oidcSpecific.post('/oidc/consent', (c) => consent(c.req.raw));
oidcSpecific.get('/oidc/handoff', (c) => handoff(c.req.raw));
oidcSpecific.get('/oidc/interaction', (c) => interactionDetails(c.req.raw));

// Mount specific routes first, then catch-all
const oidcApp = new Hono();
oidcApp.route('/', oidcSpecific);
oidcApp.route('/', oidc);

export default oidcApp;
