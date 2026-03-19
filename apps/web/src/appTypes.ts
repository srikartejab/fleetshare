export const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
export const customerStorageKey = 'fleetshare.activeUserId'

export type CustomerSummary = {
  userId: string
  displayName: string
  role: string
  demoBadge?: string | null
  planName: string
  monthlyIncludedHours: number
  hoursUsedThisCycle: number
  remainingHoursThisCycle: number
  renewalDate: string
  hourlyRate: number
}

export type PricingSnapshot = {
  userId?: string
  estimatedPrice: number
  allowanceStatus: string
  crossCycleBooking: boolean
  hourlyRate: number
  totalHours: number
  currentCycleHours: number
  includedHoursRemainingBefore: number
  includedHoursApplied: number
  includedHoursRemainingAfter: number
  billableHours: number
  provisionalPostMidnightHours: number
  provisionalCharge: number
  renewalDate?: string
  customerSummary?: CustomerSummary
}

export type Vehicle = {
  id: number
  vehicleId?: number
  plateNumber: string
  model: string
  zone: string
  vehicleType: string
  status: string
  stationId?: string
  stationName?: string
  stationAddress?: string
  area?: string
  latitude?: number
  longitude?: number
  distanceKm?: number
  estimatedPrice?: number
  allowanceStatus?: string
  hourlyRate?: number
  includedHoursApplied?: number
  includedHoursRemainingBefore?: number
  includedHoursRemainingAfter?: number
  billableHours?: number
  provisionalPostMidnightHours?: number
  provisionalCharge?: number
  renewalDate?: string
}

export type LocationOption = {
  id: string
  label: string
  address: string
  area: string
  latitude: number
  longitude: number
}

export type VehicleFilters = {
  locations: string[]
  vehicleTypes: string[]
  locationOptions?: LocationOption[]
}

export type SearchStation = {
  stationId: string
  stationName: string
  stationAddress: string
  area: string
  latitude: number
  longitude: number
  distanceKm: number
  totalVehicleCount: number
  operationalAvailableCount: number
  availableVehicleCount: number
  availableVehicleTypes: string[]
  minEstimatedPrice?: number | null
  nextAvailableTiming?: string | null
  featuredVehicle?: Vehicle | null
  vehicleList: Vehicle[]
}

export type MapCenter = {
  latitude: number
  longitude: number
}

export type Booking = {
  bookingId: number
  userId: string
  vehicleId: number
  pickupLocation: string
  startTime: string
  endTime: string
  status: string
  displayedPrice: number
  finalPrice: number
  crossCycleBooking: boolean
  refundPendingOnRenewal: boolean
  reconciliationStatus: string
  tripId?: number
  bookingNote?: string | null
  cancellationReason?: string | null
  pricingSnapshot?: PricingSnapshot
}

export type Trip = {
  tripId: number
  bookingId: number
  vehicleId: number
  userId: string
  status: string
  startedAt: string
  endedAt?: string | null
  durationHours: number
  disruptionReason?: string | null
}

export type Payment = {
  paymentId: number
  bookingId?: number | null
  tripId?: number | null
  userId: string
  amount: number
  reason: string
  status: string
}

export type Notification = {
  notificationId: number
  userId: string
  bookingId?: number | null
  tripId?: number | null
  audience: string
  subject: string
  message: string
}

export type Ticket = {
  ticketId: number
  vehicleId: number
  damageSeverity: string
  damageType: string
  estimatedDurationHours: number
  status: string
}

export type RecordItem = {
  recordId: number
  bookingId?: number | null
  tripId?: number | null
  vehicleId: number
  recordType: string
  notes?: string | null
  severity: string
  reviewState: string
  confidence: number
  detectedDamage: string[]
}

export type SearchResponse = {
  vehicleList: Vehicle[]
  estimatedPrice: number
  availabilitySummary: string
  selectedStationId?: string
  mapCenter?: MapCenter
  stationList: SearchStation[]
}

export type InspectionSubmissionResult = {
  recordId: number
  bookingId: number
  vehicleId: number
  assessmentResult: {
    severity: string
    confidence: number
    detectedDamage: string[]
  }
  tripStatus: 'CLEARED' | 'BLOCKED'
  warningMessage: string
  manualReview: boolean
}

export type InspectionCancellationResult = {
  bookingId: number
  vehicleId: number
  recordId: number
  status: string
  message: string
}

export type InternalDamageResult = {
  recordId: number
  assessmentResult: {
    severity: string
    faultType: string
  }
  severity: string
  recommendedAction: string
  blocked: boolean
  duplicateSuppressed: boolean
  incidentPublished: boolean
  bookingId?: number | null
  tripId?: number | null
  userId?: string | null
}

export type PostTripInspectionResult = {
  recordId: number
  bookingId: number
  tripId: number
  vehicleId: number
  assessmentResult: {
    severity: string
    confidence: number
    detectedDamage: string[]
  }
  followUpRequired: boolean
  warningMessage: string
  manualReview: boolean
}

export type EndTripResult = {
  tripStatus: string
  vehicleLocked: boolean
  adjustedFare: number
  refundPending: boolean
  discountAmount: number
  allowanceHoursApplied: number
  customerSummary: CustomerSummary
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const method = (options?.method ?? 'GET').toUpperCase()
  const retryableStatuses = new Set([404, 408, 429, 502, 503, 504])
  const maxAttempts = method === 'GET' ? 4 : 1
  let lastError: Error | null = null

  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const response = await fetch(`${apiBase}${path}`, options)
    if (response.ok) {
      return response.json() as Promise<T>
    }

    const text = await response.text()
    lastError = new Error(text || `Request failed with ${response.status}`)
    if (attempt >= maxAttempts || !retryableStatuses.has(response.status)) {
      throw lastError
    }

    await sleep(250 * attempt)
  }

  throw lastError ?? new Error('Request failed')
}

export function localDateTime(hoursAhead: number) {
  const date = new Date(Date.now() + hoursAhead * 60 * 60 * 1000)
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 16)
}

export function formatMoney(value: number) {
  return `SGD ${value.toFixed(2)}`
}

export function formatHours(value: number) {
  return `${value.toFixed(1)}h`
}

export function formatDate(value?: string | null) {
  if (!value) return 'N/A'
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}

export function formatDateTime(value?: string | null) {
  if (!value) return 'N/A'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

export function formatShortDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
  }).format(new Date(value))
}
