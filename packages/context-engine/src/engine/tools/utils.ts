import { ToolNameResolver } from './ToolNameResolver';
import type { LobeToolManifest, UniformTool } from './types';

// Create a singleton instance for backward compatibility
const resolver = new ToolNameResolver();

/**
 * Generate tool calling name
 * @deprecated Use ToolNameResolver.generate() instead
 */
export const generateToolName = (
  identifier: string,
  name: string,
  type: string = 'default',
): string => {
  return resolver.generate(identifier, name, type);
};

/**
 * Ensure tool parameters are object JSON schemas and carry an explicit `required` array.
 *
 * Why: JSON Schema permits omitting `required` when nothing is required, but
 * some OpenAI-compatible upstreams (bailian, glm/zhipu) reject the field when
 * it arrives as `null` after intermediate proxies normalize the missing key.
 * Emitting `required: []` keeps the wire format consistent for strict providers.
 *
 * Some external manifests also provide `parameters` as a JSON string or another
 * non-object shape. Tool-calling providers expect an object schema, so normalize
 * invalid input to an empty object schema instead of letting provider validation
 * fail at request time.
 */
export const normalizeToolParameters = (parameters: unknown): Record<string, any> => {
  let schema = parameters;

  if (typeof schema === 'string') {
    try {
      schema = JSON.parse(schema);
    } catch {
      schema = undefined;
    }
  }

  if (!schema || typeof schema !== 'object' || Array.isArray(schema)) {
    return { properties: {}, required: [], type: 'object' };
  }

  const objectSchema = schema as Record<string, any>;
  if (objectSchema.type !== 'object') return { properties: {}, required: [], type: 'object' };
  if (Array.isArray(objectSchema.required)) return objectSchema;
  return { ...objectSchema, required: [] };
};

/**
 * Convert a tool manifest into LLM-compatible UniformTool definitions
 */
export function generateToolsFromManifest(manifest: LobeToolManifest): UniformTool[] {
  return manifest.api.map((api) => ({
    function: {
      description: api.description,
      name: new ToolNameResolver().generate(manifest.identifier, api.name, manifest.type),
      parameters: normalizeToolParameters(api.parameters),
    },
    type: 'function' as const,
  }));
}

/**
 * Validate manifest schema structure
 */
export function validateManifest(manifest: any): manifest is LobeToolManifest {
  return Boolean(
    manifest &&
    typeof manifest === 'object' &&
    typeof manifest.identifier === 'string' &&
    Array.isArray(manifest.api) &&
    manifest.api.length > 0,
  );
}

/**
 * Filter valid manifest schemas
 */
export function filterValidManifests(manifestSchemas: any[]): {
  invalid: any[];
  valid: LobeToolManifest[];
} {
  const valid: LobeToolManifest[] = [];
  const invalid: any[] = [];

  for (const manifest of manifestSchemas) {
    if (validateManifest(manifest)) {
      valid.push(manifest);
    } else {
      invalid.push(manifest);
    }
  }

  return { invalid, valid };
}
