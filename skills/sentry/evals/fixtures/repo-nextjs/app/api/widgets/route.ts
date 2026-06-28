import { NextResponse } from 'next/server'

async function loadWidgets() {
  // pretend this hits a data store
  throw new Error('widget store unavailable')
}

export async function GET() {
  try {
    const widgets = await loadWidgets()
    return NextResponse.json({ widgets })
  } catch (err) {
    // Swallow point: caught here and converted to a 500, so Next's
    // instrumentation / onRequestError hook never sees the error.
    console.error('GET /api/widgets failed', err)
    return NextResponse.json({ error: 'unavailable' }, { status: 500 })
  }
}
