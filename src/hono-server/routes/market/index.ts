import { Hono } from 'hono';

import agent from './agent';
import oidc from './oidc';
import social from './social';
import user from './user';

const market = new Hono();

market.route('/', agent);
market.route('/', social);
market.route('/', user);
market.route('/', oidc);

export default market;
