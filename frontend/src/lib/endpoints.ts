// GET and POST /demo/orders share a path but not a behaviour, so an endpoint is always identified
// by method and route together, as the backend does.

// "GET /demo/orders": a React key, a chart series name and the text shown to people, all in one.
export function endpointKey({ method, endpoint }: { method: string; endpoint: string }): string {
  return `${method} ${endpoint}`
}
