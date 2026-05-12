'use client';

import { type RouteObject } from 'react-router-dom';

import {
  BusinessDesktopRoutesWithMainLayout,
  BusinessDesktopRoutesWithoutMainLayout,
} from '@/business/client/BusinessDesktopRoutes';
import { dynamicElement, dynamicLayout, ErrorBoundary, redirectElement } from '@/utils/router';

const agentChatElement = dynamicElement(() => import('@/routes/(main)/agent'), 'Desktop > Chat');
// Desktop router configuration (declarative mode)
export const desktopRoutes: RouteObject[] = [
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
                              'Desktop > Chat > Topic > Page > Redirect',
                            ),
                            index: true,
                          },
                          {
                            element: dynamicElement(
                              () => import('@/routes/(main)/agent/[topicId]/page/[docId]'),
                              'Desktop > Chat > Topic > Page > Doc',
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
                  'Desktop > Chat > ChatLayout',
                ),
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/page'),
                  'Desktop > Chat > Invalid Page Redirect',
                ),
                path: 'page',
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/profile'),
                  'Desktop > Chat > Profile',
                ),
                path: 'profile',
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/cron/[cronId]'),
                  'Desktop > Chat > Cron Detail',
                ),
                path: 'cron/:cronId',
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/agent/channel'),
                  'Desktop > Chat > Channel',
                ),
                path: 'channel',
              },
            ],
            element: dynamicLayout(
              () => import('@/routes/(main)/agent/_layout'),
              'Desktop > Chat > Layout',
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
                element: dynamicElement(
                  () => import('@/routes/(main)/group'),
                  'Desktop > Agent Group',
                ),
                index: true,
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/group/profile'),
                  'Desktop > Agent Group > Profile',
                ),
                path: 'profile',
              },
            ],
            element: dynamicLayout(
              () => import('@/routes/(main)/group/_layout'),
              'Desktop > Group > Layout',
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
                  'Desktop > Resource > Home',
                ),
                index: true,
              },
            ],
            element: dynamicElement(
              () => import('@/routes/(main)/resource/(home)/_layout'),
              'Desktop > Resource > Home > Layout',
            ),
          },
          // Library routes (knowledge base detail)
          {
            children: [
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/resource/library'),
                  'Desktop > Resource > Library',
                ),
                index: true,
              },
              {
                element: dynamicElement(
                  () => import('@/routes/(main)/resource/library/[slug]'),
                  'Desktop > Resource > Library > Slug',
                ),
                path: ':slug',
              },
            ],
            element: dynamicElement(
              () => import('@/routes/(main)/resource/library/_layout'),
              'Desktop > Resource > Library > Layout',
            ),
            path: 'library/:id',
          },
        ],
        element: dynamicElement(
          () => import('@/routes/(main)/resource/_layout'),
          'Desktop > Resource > Layout',
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
                  'Desktop > Settings > Provider > Detail',
                ),
                path: ':providerId',
              },
            ],
            element: dynamicElement(
              () => import('@/routes/(main)/settings/provider').then((m) => m.ProviderLayout),
              'Desktop > Settings > Provider > Layout',
            ),
            path: 'provider',
          },
          // Other settings tabs
          {
            element: dynamicElement(
              () => import('@/routes/(main)/settings'),
              'Desktop > Settings > Tab',
            ),
            path: ':tab',
          },
        ],
        element: dynamicElement(
          () => import('@/routes/(main)/settings/_layout'),
          'Desktop > Settings > Layout',
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
              'Desktop > Memory > Home',
            ),
            index: true,
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/identities'),
              'Desktop > Memory > Identities',
            ),
            path: 'identities',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/contexts'),
              'Desktop > Memory > Contexts',
            ),
            path: 'contexts',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/preferences'),
              'Desktop > Memory > Preferences',
            ),
            path: 'preferences',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/experiences'),
              'Desktop > Memory > Experiences',
            ),
            path: 'experiences',
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/memory/activities'),
              'Desktop > Memory > Activities',
            ),
            path: 'activities',
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/memory/_layout'),
          'Desktop > Memory > Layout',
        ),
        errorElement: <ErrorBoundary />,
        path: 'memory',
      },

      // Admin routes
      {
        children: [
          {
            element: dynamicElement(() => import('@/routes/(main)/admin'), 'Desktop > Admin'),
            index: true,
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/admin/user-settings'),
              'Desktop > Admin > UserSettings',
            ),
            path: 'users/:userId/settings/:tab?',
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/admin/_layout'),
          'Desktop > Admin > Layout',
        ),
        errorElement: <ErrorBoundary />,
        path: 'admin',
      },

      ...BusinessDesktopRoutesWithMainLayout,

      // Tasks routes (cross-agent)
      {
        children: [
          {
            element: dynamicElement(() => import('@/routes/(main)/tasks'), 'Desktop > Tasks'),
            index: true,
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/tasks/_layout'),
          'Desktop > Tasks > Layout',
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
              'Desktop > Task Detail',
            ),
            path: ':taskId',
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/task/_layout'),
          'Desktop > Task > Layout',
        ),
        errorElement: <ErrorBoundary resetPath="/tasks" />,
        path: 'task',
      },

      // Pages routes
      {
        children: [
          {
            element: dynamicElement(() => import('@/routes/(main)/page'), 'Desktop > Page'),
            index: true,
          },
          {
            element: dynamicElement(
              () => import('@/routes/(main)/page/[id]'),
              'Desktop > Page > Detail',
            ),
            path: ':id',
          },
        ],
        element: dynamicLayout(
          () => import('@/routes/(main)/page/_layout'),
          'Desktop > Page > Layout',
        ),
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
    element: dynamicLayout(() => import('@/routes/(main)/_layout'), 'Desktop > Main > Layout'),
    errorElement: <ErrorBoundary />,
    path: '/',
  },
  // Onboarding route (outside main layout)

  ...BusinessDesktopRoutesWithoutMainLayout,
];

desktopRoutes.push({
  element: dynamicElement(() => import('@/routes/onboarding'), 'Desktop > Onboarding'),
  errorElement: <ErrorBoundary />,
  path: '/onboarding',
});

desktopRoutes.push({
  element: dynamicElement(
    () => import('@/routes/onboarding/agent'),
    'Desktop > Onboarding > Agent',
  ),
  errorElement: <ErrorBoundary />,
  path: '/onboarding/agent',
});

desktopRoutes.push({
  element: dynamicElement(
    () => import('@/routes/onboarding/classic'),
    'Desktop > Onboarding > Classic',
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
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/consent/[uid]/page'),
          'Auth > OAuth Consent',
        ),
        path: '/oauth/consent/:uid',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/device/page'),
          'Auth > OAuth Device',
        ),
        path: '/oauth/device',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/device/confirm/page'),
          'Auth > OAuth Device Confirm',
        ),
        path: '/oauth/device/confirm',
      },
      {
        element: dynamicElement(
          () => import('@/routes/(auth)/oauth/device/success/page'),
          'Auth > OAuth Device Success',
        ),
        path: '/oauth/device/success',
      },
    ],
    element: authLayout,
    errorElement: <ErrorBoundary />,
  },
];

desktopRoutes.push(...authRoutes);
