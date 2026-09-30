import axios, { isCancel } from 'axios'
import { API_URL } from '../config'
import { toApiError } from './errors'

export const REQUEST_TIMEOUT_MS = 10_000

// The one Axios instance every API module uses.
export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: REQUEST_TIMEOUT_MS,
  // Report timeouts as ETIMEDOUT; the default, ECONNABORTED, also means "aborted by the browser".
  transitional: { clarifyTimeoutError: true },
})

// Every failure leaves as an ApiError, except cancellation: TanStack Query cancels on purpose
// (for example when the window changes) and expects to see its own abort, not an error to show.
apiClient.interceptors.response.use(undefined, (error: unknown) =>
  Promise.reject(isCancel(error) ? error : toApiError(error)),
)
