const express = require('express')
const router = express.Router()

async function loadUser(id) {
  if (!id) throw new Error('missing id')
  // pretend this hits a database
  throw new Error('user store unavailable')
}

router.get('/:id', async (req, res) => {
  try {
    const user = await loadUser(req.params.id)
    res.json(user)
  } catch (err) {
    // Swallow point: the error is logged and turned into a 500 right here, so it
    // never propagates to Express's error pipeline or any global handler.
    console.error('failed to load user', err.message)
    res.status(500).json({ error: 'could_not_load_user' })
  }
})

module.exports = router
