import { beforeEach, describe, expect, it, vi } from 'vitest';

import { adminService } from './admin';

const mockRestGet = vi.hoisted(() => vi.fn());

vi.mock('@/libs/rest', () => ({
  restClient: {
    get: mockRestGet,
    put: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe('AdminService REST', () => {
  it('loads users and normalizes Python snake_case fields', async () => {
    mockRestGet.mockResolvedValueOnce([
      {
        accessed_at: '2026-05-19T10:00:00Z',
        created_at: '2026-05-18T10:00:00Z',
        email: 'admin@example.com',
        first_name: 'Admin',
        full_name: 'Admin User',
        id: 'user-1',
        is_onboarded: true,
        org_id: 'org-1',
        org_role: 'owner',
        org_slug: 'engineering',
        username: 'admin',
      },
    ]);

    const result = await adminService.listUsers({ limit: 25, offset: 5 });

    expect(mockRestGet).toHaveBeenCalledWith('/admin/users', {
      params: { limit: 25, offset: 5 },
    });
    expect(result).toEqual([
      {
        accessedAt: '2026-05-19T10:00:00Z',
        createdAt: '2026-05-18T10:00:00Z',
        email: 'admin@example.com',
        firstName: 'Admin',
        fullName: 'Admin User',
        id: 'user-1',
        isOnboarded: true,
        orgId: 'org-1',
        orgRole: 'owner',
        orgSlug: 'engineering',
        username: 'admin',
      },
    ]);
  });
});
