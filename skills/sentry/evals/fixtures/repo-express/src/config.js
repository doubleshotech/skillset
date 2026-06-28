// Per-env config. Values come from the environment; nothing secret is hardcoded.
const config = {
  port: Number(process.env.PORT) || 3000,
  nodeEnv: process.env.NODE_ENV || 'development',
  databaseUrl: process.env.DATABASE_URL || '',
}

module.exports = { config }
