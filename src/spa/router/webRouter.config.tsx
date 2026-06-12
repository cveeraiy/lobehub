'use client';

import { type RouteObject } from 'react-router-dom';

import {
  BusinessWebRoutesWithMainLayout,
  BusinessWebRoutesWithoutMainLayout,
} from '@/business/client/BusinessWebRoutes';
import { dynamicElement, dynamicLayout, ErrorBoundary, redirectElement } from '@/utils/router';

const agentChatElement = dynamicElement(() => import('@/routes/(main)/agent'), 'Web > Chat');
// Web router configuration (declarative mode)
export const webRoutes: RouteObject[] = [
  {
    children: [
      // Chat routes (agent)
      {
        children: [
          {
            element: redirectElement('/'),
            index: true,
          },
          {
            children: [
              {
                children: [
                  {
                    element: agentChatElement,
                    index: true,
                  },
                  {
                    children: [
                      {
                        element: agentChatElement,
                        index: true,
                      },
                      {
                        children: [
                          {
                            element: dynamicElement(
                              () => import('@/routes/(main)/agent/[topicId]/page'),
                              'Web > Chat > Topic > Page > Redirect',
                            ),
                            index: true,
                          },
                          {
                            element: dynamicElement(
                              () => import('@/routes/(main)/agent/[topicId]/page/[docId]'),
                              'Web > Chat > Topic > Page > Doc',
                            ),
                            path: ':docId',
                          },
                        ],
                        path: 'page',
                      },
                    ],
                    path: ':topicId',
                  },
                ],
                element: dynamicLayout(
                  () => import('@/routes/(main)/agent/(chat)/_layout'),
                  'Web > Chat > ChatLayout',
                ),
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/page'),
                  'Web > Chat > Invalid Page Redirect',
                ),
                path: 'page',
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/profile'),
                  'Web > Chat > Profile',
                ),
                path: 'profile',
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/cron/[cronId]'),
                  'Web > Chat > Cron Detail',
                ),
                path: 'cron/:cronId',
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/channel'),
                  'Web > Chat > Channel',
                ),
                path: 'channel',
              },
            ],
            element: dynamicLayout(
              () => import('@/routes/(main)/agent/_layout'),
              'Web > Chat > Layout',
            ),
            errorElement: <ErrorBoundary />,
            path: ':aid',
          },
        ],
        path: 'agent',
      },

      // Group chat routes
      {
        children: [
          {
            element: redirectElement('/'),
            index: true,
          },
          {
            children: [
              {
                element: dynamicElement(() => import('@/routes/(main)/group'), 'Web > Agent Group'),
                index: true,
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/group/profile'),
                  'Web > Agent Group > Profile',
                ),
                path: 'profile',
              },
            ],
            element: dynamicLayout(
              () => import('@/routes/(main)/group/_layout'),
              'Web > Group > Layout',
            ),
            errorElement: <ErrorBoundary />,
            path: ':gid',
          },
        ],
        path: 'group',
      },

      // Resource routes
      {
        children: [
          // Home routes (resource list)
          {
            children: [
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/resource/(home)'),
                  'Web > Resource > Home',
                ),
                index: true,
              },
            ],
            element: dynamicElement(
              () => import('@/routes/(main)/resource/(home)/_layout'),
              'Web > Resource > Home > Layout',
            ),
          },
          // Library routes (knowledge base detail)
          {
            children: [
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/resource/library'),
                  'Web > Resource > Library',
                ),
                index: true,
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/resource/library/[slug]'),
                  'Web > Resource > Library > Slug',
                ),
                path: ':slug',
              },
            ],
            element: dynamicElement(
              () => import('@/routes/(main)/resource/library/_layout'),
              'Web > Resource > Library > Layout',
            ),
            path: 'library/:id',
          },
        ],
        element: dynamicElement(
          () => import('@/routes/(main)/resource/_layout'),
          'Web > Resource > Layout',
        ),
        errorElement: <ErrorBoundary />,
        path: 'resource',
      },

      // Settings routes
      {
        children: [
          {
            element: redirectElement('/settings/profile'),
            index: true,
          },
          // Provider routes with nested structure
          {
            children: [
              {
                element: redirectElement('/settings/provider/all'),
                index: true,
              },
              {
                element: dynamicElement(
                  () =>
                    import('@/routes/(main)/settings/provider').then((m) => m.ProviderDetailPage),
                  'Web > Settings > Provider > Detail',
                ),
                path: ':providerId',
              },
            ],
            element: dynamicElement(
              () => import('@/routes/(main)/settings/provider').then((m) => m.ProviderLayout),
              'Web > Settings > Provider > Layout',
            ),
            path: 'provider',
          },
          // Other settings tabs
          {
            element: dynamicElement(
              () => import('@/routes/(main)/settings'),
              'Web > Settings > Tab',
            ),
            path: ':tab',
          },
        ],
        element: dynamicElement(
          () => import('@/routes/(main)/settings/_layout'),
          'Web > Settings > Layout',
        ),
        errorElement: <ErrorBoundary />,
        path: 'settings',
      },

      // Memory routes
      {
        children: [
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/(home)'),
              'Web > Memory > Home',
            ),
            index: true,
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/identities'),
              'Web > Memory > Identities',
            ),
            path: 'identities',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/contexts'),
              'Web > Memory > Contexts',
            ),
            path: 'contexts',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/preferences'),
              'Web > Memory > Preferences',
            ),
            path: 'preferences',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/experiences'),
              'Web > Memory > Experiences',
            ),
            path: 'experiences',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/activities'),
              'Web > Memory > Activities',
            ),
            path: 'activities',
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/memory/_layout'),
          'Web > Memory > Layout',
        ),
        errorElement: <ErrorBoundary />,
        path: 'memory',
      },

      // Admin routes
      {
        children: [
          {
            element: dynamicElement(() => import('@/routes/(main)/admin'), 'Web > Admin'),
            index: true,
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/admin/user-settings'),
              'Web > Admin > UserSettings',
            ),
            path: 'users/:userId/settings/:tab?',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/admin/ai-governance'),
              'Web > Admin > AiGovernance',
            ),
            path: 'ai-governance',
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/admin/_layout'),
          'Web > Admin > Layout',
        ),
        errorElement: <ErrorBoundary />,
        path: 'admin',
      },

      ...BusinessWebRoutesWithMainLayout,

      // Tasks routes (cross-agent)
      {
        children: [
          {
            element: dynamicElement(() => import('@/routes/(main)/tasks'), 'Web > Tasks'),
            index: true,
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/tasks/_layout'),
          'Web > Tasks > Layout',
        ),
        errorElement: <ErrorBoundary resetPath="/" />,
        path: 'tasks',
      },

      // Task detail route (cross-agent entry — resolves by task identifier)
      {
        children: [
          {
            element: dynamicElement(
              () => import('@/routes/(main)/task/[taskId]'),
              'Web > Task Detail',
            ),
            path: ':taskId',
          },
        ],
        element: dynamicLayout(() => import('@/routes/(main)/task/_layout'), 'Web > Task > Layout'),
        errorElement: <ErrorBoundary resetPath="/tasks" />,
        path: 'task',
      },

      // Pages routes
      {
        children: [
          {
            element: dynamicElement(() => import('@/routes/(main)/page'), 'Web > Page'),
            index: true,
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/page/[id]'),
              'Web > Page > Detail',
            ),
            path: ':id',
          },
        ],
        element: dynamicLayout(() => import('@/routes/(main)/page/_layout'), 'Web > Page > Layout'),
        errorElement: <ErrorBoundary />,
        path: 'page',
      },

      // Default route - home page (handled by persistent layout)
      {
        index: true,
      },
      // Catch-all route
      {
        element: redirectElement('/'),
        path: '*',
      },
    ],
    element: dynamicLayout(() => import('@/routes/(main)/_layout'), 'Web > Main > Layout'),
    errorElement: <ErrorBoundary />,
    path: '/',
  },
  // Onboarding route (outside main layout)

  ...BusinessWebRoutesWithoutMainLayout,
];

webRoutes.push({
  element: dynamicElement(() => import('@/routes/onboarding'), 'Web > Onboarding'),
  errorElement: <ErrorBoundary />,
  path: '/onboarding',
});

webRoutes.push({
  element: dynamicElement(() => import('@/routes/onboarding/agent'), 'Web > Onboarding > Agent'),
  errorElement: <ErrorBoundary />,
  path: '/onboarding/agent',
});

webRoutes.push({
  element: dynamicElement(
    () => import('@/routes/onboarding/classic'),
    'Web > Onboarding > Classic',
  ),
  errorElement: <ErrorBoundary />,
  path: '/onboarding/classic',
});

// ============ Auth Routes ============ //
// Auth pages migrated from Next.js SSR to SPA client components.
// Wrapped in AuthLayout which provides NuqsAdapter + BusinessAuthProvider + AuthContainer shell.
const authLayout = dynamicLayout(() => import('@/routes/(auth)/layout'), 'Auth > Layout');

const authRoutes: RouteObject[] = [
  {
    children: [
      {
        element: dynamicElement(() => import('@/routes/(auth)/signin/page'), 'Auth > Signin'),
        path: '/signin',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/signup/[[...signup]]/page'),
          'Auth > Signup',
        ),
        path: '/signup/*',
      },
      {
        children: [
          {
            element: dynamicElement(
              () => import('@/routes/(auth)/reset-password/page'),
              'Auth > Reset Password',
            ),
            index: true,
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(auth)/reset-password/layout'),
          'Auth > Reset Password > Layout',
        ),
        path: '/reset-password',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/verify-email/page'),
          'Auth > Verify Email',
        ),
        path: '/verify-email',
      },
      {
        element: dynamicElement(() => import('@/routes/(auth)/auth-error/page'), 'Auth > Error'),
        path: '/auth-error',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/market-auth-callback/page'),
          'Auth > Market Callback',
        ),
        path: '/market-auth-callback',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/callback/error/page'),
          'Auth > OAuth Callback Error',
        ),
        path: '/oauth/callback/error',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/callback/social/page'),
          'Auth > OAuth Callback Social',
        ),
        path: '/oauth/callback/social',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/callback/success/page'),
          'Auth > OAuth Callback Success',
        ),
        path: '/oauth/callback/success',
      },
    ],
    element: authLayout,
    errorElement: <ErrorBoundary />,
  },
];

webRoutes.push(...authRoutes);
