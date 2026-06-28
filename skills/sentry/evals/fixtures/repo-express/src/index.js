const express = require('express')
const { config } = require('./config')
const usersRouter = require('./routes/users')

const app = express()
app.use(express.json())

app.get('/health', (req, res) => res.json({ ok: true }))
app.use('/users', usersRouter)

// Centralized error handler. NOTE: it swallows the error — it returns a 500 and
// does NOT rethrow or call next(err). Anything that reaches here never escapes
// the app, so nothing outside Express can observe it.
app.use((err, req, res, next) => {
  console.error('request failed:', err.message)
  res.status(500).json({ error: 'internal_error' })
})

if (require.main === module) {
  app.listen(config.port, () => console.log(`api listening on ${config.port}`))
}

module.exports = app
