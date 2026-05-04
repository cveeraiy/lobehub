'use client';

import { Accordion, AccordionItem, Flexbox, Text } from '@lobehub/ui';
import { Spin, Tag } from 'antd';
import { ArrowLeft } from 'lucide-react';
import { Fragment, memo, useMemo } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import AdminStats from '@/features/Admin/AdminStats';
import { AdminViewProvider, useAdminViewContext } from '@/features/Admin/AdminViewContext';
import NavHeader from '@/features/NavHeader';
import { NavPanelPortal } from '@/features/NavPanel';
import NavItem from '@/features/NavPanel/components/NavItem';
import SideBarLayout from '@/features/NavPanel/SideBarLayout';
import SettingContainer from '@/features/Setting/SettingContainer';
import SettingsContextProvider from '@/routes/(main)/settings/_layout/ContextProvider';
import { componentMap } from '@/routes/(main)/settings/features/componentMap';
import { SettingsGroupKey, useCategory } from '@/routes/(main)/settings/hooks/useCategory';
import type { SettingsTabs } from '@/store/global/initialState';
import { isModifierClick } from '@/utils/navigation';

const AdminSettingsSidebar = memo(() => {
  const categoryGroups = useCategory();
  const navigate = useNavigate();
  const location = useLocation();
  const { userId } = useParams<{ userId: string }>();
  const ctx = useAdminViewContext();

  const activeTab = useMemo(() => {
    // pathname: /admin/users/:userId/settings/:tab
    const match = location.pathname.match(/\/admin\/users\/[^/]+\/settings\/(.+)/);
    return (match?.[1] ?? 'profile') as SettingsTabs;
  }, [location.pathname]);

  const getTabUrl = (tab: SettingsTabs) => {
    return `/admin/users/${userId}/settings/${tab}`;
  };

  const userName = ctx?.targetUserState?.fullName || ctx?.targetUserState?.username || 'User';

  return (
    <Flexbox gap={8} paddingInline={4}>
      <Flexbox gap={4} paddingBlock={8} paddingInline={8}>
        <Link
          style={{ color: 'inherit', textDecoration: 'none' }}
          to="/admin"
          onClick={(e) => {
            if (isModifierClick(e)) return;
            e.preventDefault();
            navigate('/admin');
          }}
        >
          <Flexbox horizontal align={'center'} gap={6} style={{ cursor: 'pointer', opacity: 0.6 }}>
            <ArrowLeft size={14} />
            <Text fontSize={12}>Back to Admin</Text>
          </Flexbox>
        </Link>
        <Text style={{ lineHeight: 1.3 }} weight={'bold'}>
          {userName}
        </Text>
        <Tag color="blue" style={{ alignSelf: 'flex-start' }}>
          Read-only
        </Tag>
      </Flexbox>

      <Accordion
        gap={8}
        defaultExpandedKeys={[
          SettingsGroupKey.General,
          SettingsGroupKey.Agent,
          SettingsGroupKey.System,
        ]}
      >
        {categoryGroups.map((group) => (
          <AccordionItem
            itemKey={group.key}
            key={group.key}
            paddingBlock={4}
            paddingInline={'8px 4px'}
            title={
              <Text ellipsis fontSize={12} type={'secondary'} weight={500}>
                {group.title}
              </Text>
            }
          >
            <Flexbox gap={1} paddingBlock={1}>
              {group.items.map((item) => {
                const url = getTabUrl(item.key);
                return (
                  <Link
                    key={item.key}
                    to={url}
                    onClick={(e) => {
                      if (isModifierClick(e)) return;
                      e.preventDefault();
                      navigate(url);
                    }}
                  >
                    <NavItem active={activeTab === item.key} icon={item.icon} title={item.label} />
                  </Link>
                );
              })}
            </Flexbox>
          </AccordionItem>
        ))}
      </Accordion>
    </Flexbox>
  );
});

AdminSettingsSidebar.displayName = 'AdminSettingsSidebar';

const AdminSettingsContent = memo<{ activeTab: string }>(({ activeTab }) => {
  const ctx = useAdminViewContext();

  if (!ctx || ctx.isLoading) {
    return (
      <Flexbox align={'center'} height={'100%'} justify={'center'} width={'100%'}>
        <Spin size="large" />
      </Flexbox>
    );
  }

  // Use admin-specific stats component that reads from AdminViewContext
  if (activeTab === 'stats') {
    return (
      <Fragment>
        <NavHeader />
        <SettingContainer maxWidth={1024} paddingBlock={'24px 128px'} paddingInline={24}>
          <AdminStats />
        </SettingContainer>
      </Fragment>
    );
  }

  const Component = componentMap[activeTab as keyof typeof componentMap] || componentMap.appearance;
  if (!Component) return null;

  return (
    <Fragment>
      <NavHeader />
      <SettingContainer maxWidth={1024} paddingBlock={'24px 128px'} paddingInline={24}>
        <Component />
      </SettingContainer>
    </Fragment>
  );
});

AdminSettingsContent.displayName = 'AdminSettingsContent';

const AdminUserSettings = memo(() => {
  const { userId, tab } = useParams<{ tab?: string; userId: string }>();

  if (!userId) return null;

  return (
    <AdminViewProvider targetUserId={userId}>
      <SettingsContextProvider value={{ showOpenAIApiKey: true, showOpenAIProxyUrl: true }}>
        <NavPanelPortal navKey="admin-user-settings">
          <SideBarLayout body={<AdminSettingsSidebar />} />
        </NavPanelPortal>
        <Flexbox
          flex={1}
          height={'100%'}
          style={{ background: 'var(--ant-color-bg-container)', overflow: 'auto' }}
        >
          <AdminSettingsContent activeTab={tab || 'profile'} />
        </Flexbox>
      </SettingsContextProvider>
    </AdminViewProvider>
  );
});

AdminUserSettings.displayName = 'AdminUserSettings';

export default AdminUserSettings;
