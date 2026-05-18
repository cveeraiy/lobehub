import { App, Descriptions, Drawer, Spin, Switch } from 'antd';
import { createStaticStyles } from 'antd-style';
import { Bot, Monitor, Settings } from 'lucide-react';
import { memo, useCallback, useEffect, useState } from 'react';

import { adminService } from '@/services/admin.resolved';

interface UserSettingsDrawerProps {
  onClose: () => void;
  open: boolean;
  userId: string | null;
}

interface SettingsPermissions {
  agentSettings: boolean;
  systemSettings: boolean;
}

const styles = createStaticStyles(({ css, cssVar }) => ({
  section: css`
    margin-block-end: 24px;
  `,
  sectionTitle: css`
    display: flex;
    gap: 8px;
    align-items: center;

    margin-block: 0 12px;
    margin-inline: 0;

    font-size: 15px;
    font-weight: 600;
    color: ${cssVar.colorText};
  `,
  permRow: css`
    display: flex;
    align-items: center;
    justify-content: space-between;

    margin-block-end: 8px;
    padding-block: 14px;
    padding-inline: 16px;
    border-radius: 10px;

    background: ${cssVar.colorFillQuaternary};
  `,
  permInfo: css`
    display: flex;
    flex-direction: column;
    gap: 2px;
  `,
  permLabel: css`
    display: flex;
    gap: 8px;
    align-items: center;

    font-size: 14px;
    font-weight: 500;
    color: ${cssVar.colorText};
  `,
  permDesc: css`
    font-size: 12px;
    color: ${cssVar.colorTextTertiary};
  `,
}));

const UserSettingsDrawer = memo<UserSettingsDrawerProps>(({ open, onClose, userId }) => {
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState<any>(null);
  const [permissions, setPermissions] = useState<SettingsPermissions>({
    agentSettings: false,
    systemSettings: false,
  });
  const { message } = App.useApp();

  const fetchSettings = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const result = await adminService.getUserSettings(userId);
      setSettings(result.settings);
      setPermissions(result.permissions ?? { agentSettings: false, systemSettings: false });
    } catch {
      message.error('Failed to load user settings');
    } finally {
      setLoading(false);
    }
  }, [userId, message]);

  useEffect(() => {
    if (open && userId) {
      fetchSettings();
    }
  }, [open, userId, fetchSettings]);

  const handlePermissionChange = async (key: keyof SettingsPermissions, value: boolean) => {
    if (!userId) return;
    const newPermissions = { ...permissions, [key]: value };
    setPermissions(newPermissions);
    try {
      await adminService.updateUserPermissions(userId, newPermissions);
      message.success('Permissions updated');
    } catch {
      message.error('Failed to update permissions');
      setPermissions(permissions);
    }
  };

  return (
    <Drawer open={open} title="User Settings" width={480} onClose={onClose}>
      {loading ? (
        <Spin style={{ display: 'block', marginTop: 40, textAlign: 'center' }} />
      ) : (
        <>
          <div className={styles.section}>
            <h4 className={styles.sectionTitle}>
              <Settings size={16} />
              General Settings
            </h4>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="Language">
                {settings?.general?.language || 'auto'}
              </Descriptions.Item>
              <Descriptions.Item label="Font Size">
                {settings?.general?.fontSize ?? 14}
              </Descriptions.Item>
              <Descriptions.Item label="Theme Mode">
                {settings?.general?.themeMode || 'auto'}
              </Descriptions.Item>
            </Descriptions>
          </div>

          <div className={styles.section}>
            <h4 className={styles.sectionTitle}>
              <Settings size={16} />
              Settings Permissions
            </h4>
            <div className={styles.permRow}>
              <div className={styles.permInfo}>
                <span className={styles.permLabel}>
                  <Bot size={16} />
                  Agent Settings
                </span>
                <span className={styles.permDesc}>
                  Allow this user to access and modify agent configuration settings.
                </span>
              </div>
              <Switch
                checked={permissions.agentSettings}
                onChange={(v) => handlePermissionChange('agentSettings', v)}
              />
            </div>
            <div className={styles.permRow}>
              <div className={styles.permInfo}>
                <span className={styles.permLabel}>
                  <Monitor size={16} />
                  System Settings
                </span>
                <span className={styles.permDesc}>
                  Allow this user to access and modify system-level settings.
                </span>
              </div>
              <Switch
                checked={permissions.systemSettings}
                onChange={(v) => handlePermissionChange('systemSettings', v)}
              />
            </div>
          </div>
        </>
      )}
    </Drawer>
  );
});

UserSettingsDrawer.displayName = 'UserSettingsDrawer';

export default UserSettingsDrawer;
