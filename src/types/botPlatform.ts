export type ConnectionMode = 'polling' | 'webhook' | 'websocket';

export interface FieldSchema {
  default?: unknown;
  description?: string;
  devOnly?: boolean;
  enum?: string[];
  enumDescriptions?: string[];
  enumLabels?: string[];
  items?: FieldSchema;
  key: string;
  label: string;
  maximum?: number;
  minimum?: number;
  placeholder?: string;
  properties?: FieldSchema[];
  required?: boolean;
  tooltip?: string;
  type: 'array' | 'boolean' | 'integer' | 'number' | 'object' | 'password' | 'string';
  visibleWhen?: { field: string; value: unknown };
}

export interface PlatformDocumentation {
  portalUrl?: string;
  setupGuideUrl?: string;
}

export interface SerializedPlatformDefinition {
  connectionMode: ConnectionMode;
  description?: string;
  documentation?: PlatformDocumentation;
  id: string;
  name: string;
  schema: FieldSchema[];
  showWebhookUrl?: boolean;
  supportsMarkdown?: boolean;
  supportsMessageEdit?: boolean;
}
