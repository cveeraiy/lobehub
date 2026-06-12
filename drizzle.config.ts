import * as dotenv from 'dotenv';
import type { Config } from 'drizzle-kit';

// Read the .env file if it exists, or a file specified by the

// dotenv_config_path parameter that's passed to Node.js

dotenv.config();

const connectionString = process.env.DATABASE_URL!;

export default {
  dbCredentials: {
    url: connectionString,
  },
  dialect: 'postgresql',
  out: './src/database/migrations',

  schema: './src/database/schemas',
  strict: true,
} satisfies Config;
