'use client';

import { Flexbox, Tag } from '@lobehub/ui';
import {
  App,
  Button,
  Checkbox,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  type TableColumnType,
} from 'antd';
import { createStaticStyles } from 'antd-style';
import { ArrowLeft, Pencil, Plus, ShieldCheck, SlidersHorizontal, Trash2 } from 'lucide-react';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { adminService } from '@/services/admin';
import { aiProviderService } from '@/services/aiProvider';
import type {
  EnterpriseAiPolicy,
  EnterpriseAiPolicyInput,
  EnterpriseAiPolicyTarget,
} from '@/services/enterpriseAiPolicy';
import { enterpriseAiPolicyService } from '@/services/enterpriseAiPolicy';
import { agentSkillService } from '@/services/skill';

interface PolicyFormValues {
  allowModels?: string[];
  allowSkills?: string[];
  defaultModel?: string;
  defaultProvider?: string;
  denyModels?: string[];
  description?: string;
  enabled: boolean;
  manageModel?: boolean;
  manageProvider?: boolean;
  manageSkills?: boolean;
  name: string;
  priority: number;
  targetId?: string;
  targetType?: EnterpriseAiPolicyTarget['targetType'];
}

interface GovernanceOptions {
  groups: { label: string; value: string }[];
  models: { label: string; providerId: string; value: string }[];
  organizations: { label: string; value: string }[];
  providers: { label: string; value: string }[];
  skills: { label: string; value: string }[];
  users: { label: string; value: string }[];
}

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
    gap: 16px;
    align-items: flex-start;
    justify-content: space-between;
  `,
  headerMain: css`
    display: flex;
    flex-direction: column;
    gap: 6px;
  `,
  backButton: css`
    cursor: pointer;

    display: inline-flex;
    gap: 6px;
    align-items: center;

    width: fit-content;
    margin-block-end: 8px;
    padding: 0;
    border: 0;

    font-size: 13px;
    color: ${cssVar.colorTextTertiary};

    background: transparent;
  `,
  title: css`
    display: flex;
    gap: 10px;
    align-items: center;

    margin: 0;

    font-size: 22px;
    font-weight: 600;
    color: ${cssVar.colorText};
  `,
  description: css`
    max-width: 720px;
    margin: 0;

    font-size: 14px;
    line-height: 1.5;
    color: ${cssVar.colorTextTertiary};
  `,
  summaryGrid: css`
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
  `,
  summaryItem: css`
    display: flex;
    gap: 12px;
    align-items: center;

    padding-block: 16px;
    padding-inline: 20px;
    border-radius: 8px;

    background: ${cssVar.colorFillQuaternary};
  `,
  summaryIcon: css`
    display: flex;
    align-items: center;
    justify-content: center;

    width: 38px;
    height: 38px;
    border-radius: 8px;

    color: ${cssVar.colorTextSecondary};

    background: ${cssVar.colorFillTertiary};
  `,
  summaryValue: css`
    font-size: 20px;
    font-weight: 600;
    line-height: 1.1;
    color: ${cssVar.colorText};
  `,
  summaryLabel: css`
    font-size: 12px;
    color: ${cssVar.colorTextTertiary};
  `,
  tableWrap: css`
    overflow: hidden;
    border: 1px solid ${cssVar.colorBorderSecondary};
    border-radius: 8px;
  `,
  drawerSection: css`
    margin-block-end: 24px;
  `,
  drawerSectionTitle: css`
    margin-block: 0 12px;
    margin-inline: 0;

    font-size: 14px;
    font-weight: 600;
    color: ${cssVar.colorText};
  `,
}));

const emptyOptions: GovernanceOptions = {
  groups: [],
  models: [],
  organizations: [],
  providers: [],
  skills: [],
  users: [],
};

const toStringArray = (value: unknown) =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];

const createEmptyPolicyInput = (values: PolicyFormValues): EnterpriseAiPolicyInput => {
  const allowModels = toStringArray(values.allowModels);
  const denyModels = toStringArray(values.denyModels);
  const allowSkills = toStringArray(values.allowSkills);
  const modelConfig: Record<string, unknown> = {};
  const restrictions: Record<string, unknown> = {};
  const skillConfig: Record<string, unknown> = {};

  if (values.defaultModel || values.defaultProvider) {
    modelConfig.default_agent = {
      ...(values.defaultModel ? { model: values.defaultModel } : {}),
      ...(values.defaultProvider ? { provider: values.defaultProvider } : {}),
    };
  }
  if (allowModels.length > 0) modelConfig.allow = allowModels;
  if (denyModels.length > 0) restrictions.deny_models = denyModels;
  if (allowSkills.length > 0) skillConfig.allow = allowSkills;

  return {
    description: values.description,
    enabled: values.enabled,
    managedSettings: {
      model: !!values.manageModel,
      provider: !!values.manageProvider,
      skills: !!values.manageSkills,
    },
    modelConfig,
    name: values.name,
    priority: values.priority,
    providerConfig: {},
    restrictions,
    skillConfig,
    targets:
      values.targetType && values.targetId
        ? [{ targetId: values.targetId, targetType: values.targetType }]
        : [],
  };
};

const policyToFormValues = (policy?: EnterpriseAiPolicy): PolicyFormValues => {
  const defaultAgent = (policy?.modelConfig.default_agent || {}) as Record<string, string>;

  return {
    allowModels: toStringArray(policy?.modelConfig.allow),
    allowSkills: toStringArray(policy?.skillConfig.allow),
    defaultModel: defaultAgent.model,
    defaultProvider: defaultAgent.provider,
    denyModels: toStringArray(policy?.restrictions.deny_models),
    description: policy?.description || undefined,
    enabled: policy?.enabled ?? true,
    manageModel: policy?.managedSettings.model ?? true,
    manageProvider: policy?.managedSettings.provider ?? true,
    manageSkills: policy?.managedSettings.skills ?? true,
    name: policy?.name || '',
    priority: policy?.priority ?? 0,
    targetId: policy?.targets[0]?.targetId,
    targetType: policy?.targets[0]?.targetType || 'organization',
  };
};

const ManagedTags = memo<{ policy: EnterpriseAiPolicy }>(({ policy }) => {
  const items = [
    policy.managedSettings.provider ? 'Provider' : undefined,
    policy.managedSettings.model ? 'Model' : undefined,
    policy.managedSettings.skills ? 'Skill' : undefined,
  ].filter(Boolean);

  if (items.length === 0) return <Tag>None</Tag>;

  return (
    <Space wrap size={4}>
      {items.map((item) => (
        <Tag color="blue" key={item}>
          {item}
        </Tag>
      ))}
    </Space>
  );
});

ManagedTags.displayName = 'ManagedTags';

const Targets = memo<{ targets: EnterpriseAiPolicyTarget[] }>(({ targets }) => {
  if (targets.length === 0) return <Tag>Global</Tag>;

  return (
    <Space wrap size={4}>
      {targets.map((target) => (
        <Tag key={`${target.targetType}:${target.targetId}`}>
          {target.targetType}: {target.targetId}
        </Tag>
      ))}
    </Space>
  );
});

Targets.displayName = 'Targets';

const AiGovernance = memo(() => {
  const [form] = Form.useForm<PolicyFormValues>();
  const [policies, setPolicies] = useState<EnterpriseAiPolicy[]>([]);
  const [options, setOptions] = useState<GovernanceOptions>(emptyOptions);
  const [loading, setLoading] = useState(true);
  const [optionsLoading, setOptionsLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState<EnterpriseAiPolicy | undefined>();
  const { message } = App.useApp();
  const navigate = useNavigate();
  const defaultProvider = Form.useWatch('defaultProvider', form);
  const targetType = Form.useWatch('targetType', form);

  const loadPolicies = useCallback(async () => {
    setLoading(true);
    try {
      const list = await enterpriseAiPolicyService.listPolicies();
      setPolicies(list);
    } catch (error) {
      console.error(error);
      message.error('Failed to load AI governance policies.');
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    loadPolicies();
  }, [loadPolicies]);

  const loadOptions = useCallback(async () => {
    setOptionsLoading(true);
    try {
      const [runtimeState, skillList, users, groupTargets] = await Promise.all([
        aiProviderService.getAiProviderRuntimeState(true),
        agentSkillService.list(),
        adminService.listUsers({ limit: 200 }),
        enterpriseAiPolicyService.listGroupTargets(),
      ]);

      const providers = runtimeState.enabledChatAiProviders.map((provider) => ({
        label: provider.name || provider.id,
        value: provider.id,
      }));
      const providerIds = new Set(providers.map((provider) => provider.value));
      const models = runtimeState.enabledAiModels
        .filter((model) => !providerIds.size || providerIds.has(model.providerId))
        .map((model) => ({
          label: `${model.displayName || model.id} (${model.providerId})`,
          providerId: model.providerId,
          value: model.id,
        }));
      const skills = skillList.data.map((skill) => ({
        label: `${skill.name || skill.manifest?.name || skill.identifier} (${skill.source})`,
        value: skill.identifier || skill.id,
      }));
      const userOptions = users.map((user) => {
        const name = user.email || user.username || user.fullName || user.firstName || user.id;
        return {
          label: `${name} (${user.id})`,
          value: user.id,
        };
      });
      const organizations = Array.from(
        new Map(
          users
            .flatMap((user) => {
              const items: { label: string; value: string }[] = [];
              if (user.orgId) {
                items.push({
                  label: user.orgSlug ? `${user.orgSlug} (${user.orgId})` : user.orgId,
                  value: user.orgId,
                });
              }
              if (user.orgSlug && user.orgSlug !== user.orgId) {
                items.push({ label: user.orgSlug, value: user.orgSlug });
              }
              return items;
            })
            .map((item) => [item.value, item]),
        ).values(),
      );
      const groups = groupTargets.map((groupId) => ({
        label: groupId,
        value: groupId,
      }));

      setOptions({ groups, models, organizations, providers, skills, users: userOptions });
    } catch (error) {
      console.error(error);
      message.error('Failed to load selectable policy values from the backend.');
    } finally {
      setOptionsLoading(false);
    }
  }, [message]);

  useEffect(() => {
    loadOptions();
  }, [loadOptions]);

  const defaultModelOptions = useMemo(
    () =>
      defaultProvider
        ? options.models.filter((model) => model.providerId === defaultProvider)
        : options.models,
    [defaultProvider, options.models],
  );

  const summary = useMemo(
    () => ({
      modelManaged: policies.filter((policy) => policy.managedSettings.model).length,
      providerManaged: policies.filter((policy) => policy.managedSettings.provider).length,
      skillManaged: policies.filter((policy) => policy.managedSettings.skills).length,
      total: policies.length,
    }),
    [policies],
  );

  const openCreate = () => {
    setEditingPolicy(undefined);
    form.setFieldsValue(policyToFormValues());
    setDrawerOpen(true);
  };

  const openEdit = (policy: EnterpriseAiPolicy) => {
    setEditingPolicy(policy);
    form.setFieldsValue(policyToFormValues(policy));
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
    setEditingPolicy(undefined);
  };

  const savePolicy = async () => {
    const values = await form.validateFields();
    const payload = createEmptyPolicyInput(values);

    setSaving(true);
    try {
      if (editingPolicy) {
        await enterpriseAiPolicyService.updatePolicy(editingPolicy.id, payload);
        message.success('Policy updated.');
      } else {
        await enterpriseAiPolicyService.createPolicy(payload);
        message.success('Policy created.');
      }
      closeDrawer();
      await loadPolicies();
    } catch (error) {
      console.error(error);
      message.error('Policy could not be saved. Review the fields and try again.');
    } finally {
      setSaving(false);
    }
  };

  const deletePolicy = async (policyId: string) => {
    try {
      await enterpriseAiPolicyService.deletePolicy(policyId);
      message.success('Policy deleted.');
      await loadPolicies();
    } catch (error) {
      console.error(error);
      message.error('Policy could not be deleted.');
    }
  };

  const columns: TableColumnType<EnterpriseAiPolicy>[] = [
    {
      dataIndex: 'name',
      key: 'name',
      render: (name: string, policy) => (
        <Flexbox gap={2}>
          <strong>{name}</strong>
          {policy.description ? (
            <span style={{ color: 'var(--ant-color-text-tertiary)', fontSize: 12 }}>
              {policy.description}
            </span>
          ) : null}
        </Flexbox>
      ),
      title: 'Policy',
    },
    {
      key: 'managed',
      render: (_, policy) => <ManagedTags policy={policy} />,
      title: 'Managed settings',
      width: 220,
    },
    {
      dataIndex: 'targets',
      key: 'targets',
      render: (targets: EnterpriseAiPolicyTarget[]) => <Targets targets={targets} />,
      title: 'Targets',
      width: 260,
    },
    {
      dataIndex: 'priority',
      key: 'priority',
      title: 'Priority',
      width: 100,
    },
    {
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean) => (
        <Tag color={enabled ? 'green' : 'default'}>{enabled ? 'Active' : 'Paused'}</Tag>
      ),
      title: 'Status',
      width: 120,
    },
    {
      key: 'actions',
      render: (_, policy) => (
        <Space onClick={(event) => event.stopPropagation()}>
          <Button icon={<Pencil size={14} />} size="small" onClick={() => openEdit(policy)}>
            Edit
          </Button>
          <Popconfirm
            cancelText="Keep"
            okText="Delete"
            okType="danger"
            title="Delete this policy?"
            onConfirm={() => deletePolicy(policy.id)}
          >
            <Button danger icon={<Trash2 size={14} />} size="small" />
          </Popconfirm>
        </Space>
      ),
      title: 'Actions',
      width: 170,
    },
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerMain}>
          <button className={styles.backButton} type="button" onClick={() => navigate('/admin')}>
            <ArrowLeft size={14} />
            Back to Admin
          </button>
          <h2 className={styles.title}>
            <ShieldCheck size={22} />
            AI Governance
          </h2>
          <p className={styles.description}>
            Manage provider, model, and Skill access for users, groups, or an organization.
          </p>
        </div>
        <Button icon={<Plus size={16} />} type="primary" onClick={openCreate}>
          Create policy
        </Button>
      </div>

      <div className={styles.summaryGrid}>
        <div className={styles.summaryItem}>
          <div className={styles.summaryIcon}>
            <SlidersHorizontal size={19} />
          </div>
          <Flexbox>
            <span className={styles.summaryValue}>{summary.total}</span>
            <span className={styles.summaryLabel}>Policies</span>
          </Flexbox>
        </div>
        <div className={styles.summaryItem}>
          <div className={styles.summaryIcon}>
            <ShieldCheck size={19} />
          </div>
          <Flexbox>
            <span className={styles.summaryValue}>{summary.providerManaged}</span>
            <span className={styles.summaryLabel}>Provider controls</span>
          </Flexbox>
        </div>
        <div className={styles.summaryItem}>
          <div className={styles.summaryIcon}>
            <ShieldCheck size={19} />
          </div>
          <Flexbox>
            <span className={styles.summaryValue}>{summary.modelManaged}</span>
            <span className={styles.summaryLabel}>Model controls</span>
          </Flexbox>
        </div>
        <div className={styles.summaryItem}>
          <div className={styles.summaryIcon}>
            <ShieldCheck size={19} />
          </div>
          <Flexbox>
            <span className={styles.summaryValue}>{summary.skillManaged}</span>
            <span className={styles.summaryLabel}>Skill controls</span>
          </Flexbox>
        </div>
      </div>

      <div className={styles.tableWrap}>
        <Table
          columns={columns}
          dataSource={policies}
          loading={loading}
          pagination={false}
          rowKey="id"
          locale={{
            emptyText: (
              <Empty
                description="No governance policies yet."
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
          onRow={(policy) => ({
            onClick: () => openEdit(policy),
            style: { cursor: 'pointer' },
          })}
        />
      </div>

      <Drawer
        destroyOnClose
        open={drawerOpen}
        title={editingPolicy ? 'Edit policy' : 'Create policy'}
        width={640}
        extra={
          <Space>
            <Button onClick={closeDrawer}>Cancel</Button>
            <Button loading={saving} type="primary" onClick={savePolicy}>
              Save policy
            </Button>
          </Space>
        }
        onClose={closeDrawer}
      >
        <Form form={form} initialValues={policyToFormValues()} layout="vertical" preserve={false}>
          <div className={styles.drawerSection}>
            <h3 className={styles.drawerSectionTitle}>Policy details</h3>
            <Form.Item
              label="Name"
              name="name"
              rules={[{ message: 'Name this policy before saving.', required: true }]}
            >
              <Input placeholder="Engineering default access" />
            </Form.Item>
            <Form.Item label="Description" name="description">
              <Input.TextArea autoSize={{ maxRows: 3, minRows: 2 }} />
            </Form.Item>
            <Form.Item label="Priority" name="priority">
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Status" name="enabled" valuePropName="checked">
              <Switch checkedChildren="Active" unCheckedChildren="Paused" />
            </Form.Item>
          </div>

          <div className={styles.drawerSection}>
            <h3 className={styles.drawerSectionTitle}>Managed settings</h3>
            <Space direction="vertical">
              <Form.Item noStyle name="manageProvider" valuePropName="checked">
                <Checkbox>Provider settings</Checkbox>
              </Form.Item>
              <Form.Item noStyle name="manageModel" valuePropName="checked">
                <Checkbox>Default model and model access</Checkbox>
              </Form.Item>
              <Form.Item noStyle name="manageSkills" valuePropName="checked">
                <Checkbox>Skill access</Checkbox>
              </Form.Item>
            </Space>
          </div>

          <div className={styles.drawerSection}>
            <h3 className={styles.drawerSectionTitle}>Model defaults</h3>
            <Form.Item label="Default provider" name="defaultProvider">
              <Select
                allowClear
                showSearch
                loading={optionsLoading}
                optionFilterProp="label"
                options={options.providers}
                placeholder="Select a provider"
                onChange={() => form.setFieldValue('defaultModel', undefined)}
              />
            </Form.Item>
            <Form.Item label="Default model" name="defaultModel">
              <Select
                allowClear
                showSearch
                loading={optionsLoading}
                optionFilterProp="label"
                options={defaultModelOptions}
                placeholder="Select a model"
              />
            </Form.Item>
            <Form.Item label="Allowed models" name="allowModels">
              <Select
                allowClear
                showSearch
                loading={optionsLoading}
                mode="multiple"
                optionFilterProp="label"
                options={options.models}
                placeholder="Select allowed models"
              />
            </Form.Item>
            <Form.Item label="Denied models" name="denyModels">
              <Select
                allowClear
                showSearch
                loading={optionsLoading}
                mode="multiple"
                optionFilterProp="label"
                options={options.models}
                placeholder="Select denied models"
              />
            </Form.Item>
          </div>

          <div className={styles.drawerSection}>
            <h3 className={styles.drawerSectionTitle}>Skill access</h3>
            <Form.Item label="Allowed Skills" name="allowSkills">
              <Select
                allowClear
                showSearch
                loading={optionsLoading}
                mode="multiple"
                optionFilterProp="label"
                options={options.skills}
                placeholder="Select allowed Skills"
              />
            </Form.Item>
          </div>

          <div className={styles.drawerSection}>
            <h3 className={styles.drawerSectionTitle}>Initial target</h3>
            <Form.Item label="Target type" name="targetType">
              <Select
                options={[
                  { label: 'Organization', value: 'organization' },
                  { label: 'Group', value: 'group' },
                  { label: 'User', value: 'user' },
                  { label: 'Global', value: 'global' },
                ]}
                onChange={() => form.setFieldValue('targetId', undefined)}
              />
            </Form.Item>
            {targetType === 'user' ? (
              <Form.Item label="Target user" name="targetId">
                <Select
                  allowClear
                  showSearch
                  loading={optionsLoading}
                  optionFilterProp="label"
                  options={options.users}
                  placeholder="Select a user"
                />
              </Form.Item>
            ) : targetType === 'organization' ? (
              <Form.Item label="Target organization" name="targetId">
                <Select
                  allowClear
                  showSearch
                  loading={optionsLoading}
                  optionFilterProp="label"
                  options={options.organizations}
                  placeholder="Select an organization"
                />
              </Form.Item>
            ) : targetType === 'group' ? (
              <Form.Item label="Target group" name="targetId">
                <Select
                  allowClear
                  showSearch
                  loading={optionsLoading}
                  optionFilterProp="label"
                  options={options.groups}
                  placeholder="Select a group"
                />
              </Form.Item>
            ) : targetType === 'global' ? null : (
              <Form.Item label="Target ID" name="targetId">
                <Input disabled />
              </Form.Item>
            )}
          </div>
        </Form>
      </Drawer>
    </div>
  );
});

AiGovernance.displayName = 'AiGovernance';

export default AiGovernance;
