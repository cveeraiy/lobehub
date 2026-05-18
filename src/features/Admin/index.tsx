import { Avatar, Tag } from '@lobehub/ui';
import { App, Button, Input, Popconfirm, Select, Table, type TableColumnType } from 'antd';
import { createStaticStyles } from 'antd-style';
import { Ban, CheckCircle, Search, Shield, ShieldCheck, Users } from 'lucide-react';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { admin, useSession } from '@/libs/better-auth/auth-client';

interface UserRecord {
  banned: boolean;
  email: string;
  id: string;
  image: string | null;
  name: string;
  role: AdminAssignableRole | 'super_admin';
}

type AdminAssignableRole = 'admin' | 'user';

const styles = createStaticStyles(({ css, cssVar }) => ({
  container: css`
    display: flex;
    flex-direction: column;
    gap: 24px;

    max-width: 1200px;
    margin-block: 0;
    margin-inline: auto;
    padding-block: 32px;
    padding-inline: 40px;
  `,
  header: css`
    display: flex;
    flex-direction: column;
    gap: 4px;
  `,
  headerTitle: css`
    display: flex;
    gap: 10px;
    align-items: center;

    margin: 0;

    font-size: 22px;
    font-weight: 600;
    color: ${cssVar.colorText};
  `,
  headerDesc: css`
    margin: 0;
    font-size: 14px;
    color: ${cssVar.colorTextTertiary};
  `,
  stats: css`
    display: flex;
    gap: 16px;
  `,
  statCard: css`
    display: flex;
    gap: 12px;
    align-items: center;

    min-width: 160px;
    padding-block: 16px;
    padding-inline: 20px;
    border-radius: 12px;

    background: ${cssVar.colorFillQuaternary};
  `,
  statIcon: css`
    display: flex;
    align-items: center;
    justify-content: center;

    width: 40px;
    height: 40px;
    border-radius: 10px;

    color: ${cssVar.colorTextSecondary};

    background: ${cssVar.colorFillTertiary};
  `,
  statInfo: css`
    display: flex;
    flex-direction: column;
  `,
  statValue: css`
    font-size: 20px;
    font-weight: 600;
    line-height: 1.2;
    color: ${cssVar.colorText};
  `,
  statLabel: css`
    font-size: 12px;
    color: ${cssVar.colorTextTertiary};
  `,
  toolbar: css`
    display: flex;
    gap: 12px;
    align-items: center;
  `,
}));

const AdminPanel = memo(() => {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const { message } = App.useApp();
  const { data: session } = useSession();
  const currentUserId = session?.user?.id;
  const navigate = useNavigate();

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await admin.listUsers({ query: { limit: '100' } });
      if (res.data) {
        setUsers(
          res.data.users.map((u: any) => ({
            banned: u.banned ?? false,
            email: u.email,
            id: u.id,
            image: u.image,
            name: u.name,
            role: u.role ?? 'user',
          })),
        );
      }
    } catch {
      message.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const filteredUsers = useMemo(() => {
    if (!searchQuery.trim()) return users;
    const q = searchQuery.toLowerCase();
    return users.filter(
      (u) => u.name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q),
    );
  }, [users, searchQuery]);

  const stats = useMemo(
    () => ({
      admins: users.filter((u) => u.role === 'admin' || u.role === 'super_admin').length,
      banned: users.filter((u) => u.banned).length,
      total: users.length,
    }),
    [users],
  );

  const handleRoleChange = async (userId: string, newRole: AdminAssignableRole) => {
    try {
      await admin.setRole({ role: newRole, userId });
      message.success('Role updated');
      fetchUsers();
    } catch {
      message.error('Failed to update role');
    }
  };

  const handleBan = async (userId: string) => {
    try {
      await admin.banUser({ userId });
      message.success('User banned');
      fetchUsers();
    } catch {
      message.error('Failed to ban user');
    }
  };

  const handleUnban = async (userId: string) => {
    try {
      await admin.unbanUser({ userId });
      message.success('User unbanned');
      fetchUsers();
    } catch {
      message.error('Failed to unban user');
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await admin.removeUser({ userId });
      message.success('User removed');
      fetchUsers();
    } catch {
      message.error('Failed to remove user');
    }
  };

  const handleRowClick = (record: UserRecord) => {
    navigate(`/admin/users/${record.id}/settings/profile`);
  };

  const columns: TableColumnType<UserRecord>[] = [
    {
      dataIndex: 'image',
      key: 'avatar',
      render: (image: string | null, record: UserRecord) => (
        <Avatar avatar={image || undefined} size={32} title={record.name} />
      ),
      title: '',
      width: 60,
    },
    { dataIndex: 'name', key: 'name', title: 'Name' },
    { dataIndex: 'email', key: 'email', title: 'Email' },
    {
      dataIndex: 'role',
      key: 'role',
      render: (role: UserRecord['role'], record: UserRecord) => (
        <Select<AdminAssignableRole>
          disabled={record.id === currentUserId} // Disable self-actions
          size="small"
          value={role === 'super_admin' ? 'admin' : role}
          options={[
            { label: 'User', value: 'user' },
            { label: 'Admin', value: 'admin' },
          ]}
          onChange={(value) => handleRoleChange(record.id, value)}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      title: 'Role',
      width: 120,
    },
    {
      dataIndex: 'banned',
      key: 'status',
      render: (banned: boolean) => (
        <Tag color={banned ? 'red' : 'green'}>{banned ? 'Banned' : 'Active'}</Tag>
      ),
      title: 'Status',
      width: 100,
    },
    {
      key: 'actions',
      render: (_: any, record: UserRecord) => {
        const isSelf = record.id === currentUserId;
        return (
          <div style={{ display: 'flex', gap: 8 }} onClick={(e) => e.stopPropagation()}>
            {record.banned ? (
              <Button disabled={isSelf} size="small" onClick={() => handleUnban(record.id)}>
                Unban
              </Button>
            ) : (
              <Button disabled={isSelf} size="small" onClick={() => handleBan(record.id)}>
                Ban
              </Button>
            )}
            <Popconfirm
              cancelText="Cancel"
              okText="Remove"
              okType="danger"
              title="Are you sure you want to remove this user?"
              onConfirm={() => handleRemove(record.id)}
            >
              <Button danger disabled={isSelf} size="small">
                Remove
              </Button>
            </Popconfirm>
          </div>
        );
      },
      title: 'Actions',
      width: 200,
    },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2 className={styles.headerTitle}>
          <Shield size={22} />
          User Management
        </h2>
        <p className={styles.headerDesc}>Manage users, roles, permissions, and account status.</p>
      </div>

      <div className={styles.stats}>
        <div className={styles.statCard}>
          <div className={styles.statIcon}>
            <Users size={20} />
          </div>
          <div className={styles.statInfo}>
            <span className={styles.statValue}>{stats.total}</span>
            <span className={styles.statLabel}>Total Users</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statIcon}>
            <ShieldCheck size={20} />
          </div>
          <div className={styles.statInfo}>
            <span className={styles.statValue}>{stats.admins}</span>
            <span className={styles.statLabel}>Admins</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statIcon}>
            <Ban size={20} />
          </div>
          <div className={styles.statInfo}>
            <span className={styles.statValue}>{stats.banned}</span>
            <span className={styles.statLabel}>Banned</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={styles.statIcon}>
            <CheckCircle size={20} />
          </div>
          <div className={styles.statInfo}>
            <span className={styles.statValue}>{stats.total - stats.banned}</span>
            <span className={styles.statLabel}>Active</span>
          </div>
        </div>
      </div>

      <div className={styles.toolbar}>
        <Input
          allowClear
          placeholder="Search by name or email..."
          prefix={<Search size={16} />}
          style={{ maxWidth: 360 }}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <Table
        columns={columns}
        dataSource={filteredUsers}
        loading={loading}
        rowKey="id"
        size="middle"
        onRow={(record) => ({
          onClick: () => handleRowClick(record),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  );
});

AdminPanel.displayName = 'AdminPanel';

export default AdminPanel;
