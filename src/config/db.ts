import { createEnv } from '@t3-oss/env-core';
import { z } from 'zod';

export const getServerDBConfig = () => {
  return createEnv({
    runtimeEnv: {
      DATABASE_DRIVER: process.env.DATABASE_DRIVER || 'neon',
      DATABASE_TEST_URL: process.env.DATABASE_TEST_URL,
      DATABASE_URL: process.env.DATABASE_URL,

      KEY_VAULTS_SECRET: process.env.KEY_VAULTS_SECRET,

      PYTHON_BACKEND_SERVICE_TOKEN: process.env.PYTHON_BACKEND_SERVICE_TOKEN,
      PYTHON_BACKEND_URL: process.env.PYTHON_BACKEND_URL,

      REMOVE_GLOBAL_FILE: process.env.DISABLE_REMOVE_GLOBAL_FILE !== '0',
    },
    server: {
      DATABASE_DRIVER: z.enum(['neon', 'node']),
      DATABASE_TEST_URL: z.string().optional(),
      DATABASE_URL: z.string().optional(),

      KEY_VAULTS_SECRET: z.string().optional(),

      PYTHON_BACKEND_SERVICE_TOKEN: z.string().optional(),
      PYTHON_BACKEND_URL: z.string().url().optional(),

      REMOVE_GLOBAL_FILE: z.boolean().optional(),
    },
  });
};

export const serverDBEnv = getServerDBConfig();
