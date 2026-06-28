const test = require('node:test')
const assert = require('node:assert')
const app = require('./index')

test('app module loads', () => {
  assert.strictEqual(typeof app, 'function')
})
