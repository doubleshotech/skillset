async function getWidgets() {
  const res = await fetch('http://localhost:3000/api/widgets', { cache: 'no-store' })
  return res.json()
}

export default async function Page() {
  const data = await getWidgets()
  return (
    <main>
      <h1>Widgets</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </main>
  )
}
