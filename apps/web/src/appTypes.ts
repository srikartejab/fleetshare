const configuredApiBase = import.meta.env.VITE_API_BASE_URL?.trim()
export const apiBase = configuredApiBase ? configuredApiBase.replace(/\/$/, '') : ''
export const customerStorageKey = 'fleetshare.activeUserId'
const BILLING_TIMEZONE = 'Asia/Singapore'
const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/

export type CustomerSummary = {
  userId: string
  displayName: string
  role: string
  demoBadge?: string | null
  planName: string
  monthlyIncludedHours: number
  hoursUsedThisCycle: number
  remainingHoursThisCycle: number
  subscriptionEndDate: string
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
  subscriptionEndDate?: string
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
  crossCycleBooking?: boolean
  hourlyRate?: number
  totalHours?: number
  currentCycleHours?: number
  includedHoursApplied?: number
  includedHoursRemainingBefore?: number
  includedHoursRemainingAfter?: number
  billableHours?: number
  provisionalPostMidnightHours?: number
  provisionalCharge?: number
  subscriptionEndDate?: string
}

export type ReservationDraft = {
  vehicle: Vehicle
  pickupLocationLabel: string
  startTime: string
  endTime: string
  pricing: PricingSnapshot
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
  bookingCode?: string | null
  customerName?: string | null
  vehicleName?: string | null
  stationName?: string | null
  stationAddress?: string | null
  zone?: string | null
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
  createdAt?: string | null
}

export type WalletLedgerEntry = {
  ledgerId: number
  bookingId: number
  tripId?: number | null
  userId: string
  entryType: 'USAGE' | 'RENEWAL'
  startTime?: string | null
  endTime?: string | null
  totalHours: number
  currentCycleHours: number
  includedHoursApplied: number
  includedHoursAfterRenewal: number
  restoredIncludedHours?: number
  billableHours: number
  provisionalPostMidnightHours: number
  provisionalCharge: number
  baseCharge: number
  finalPrice: number
  refundAmount: number
  discountAmount: number
  renewalPending: boolean
  reconciliationStatus: string
  createdAt?: string | null
  updatedAt?: string | null
}

export type NotificationPayload = Record<string, unknown> & {
  severity?: string | null
  primaryBookingCancelled?: boolean
  futureBookingsCancelledCount?: number
  cancelledBookingIds?: number[]
}

export type Notification = {
  notificationId: number
  userId: string
  bookingId?: number | null
  tripId?: number | null
  audience: string
  subject: string
  message: string
  payload?: NotificationPayload
  createdAt?: string | null
  bookingCode?: string | null
  customerName?: string | null
  vehicleId?: number | null
  vehicleName?: string | null
  stationName?: string | null
  stationAddress?: string | null
  zone?: string | null
  severity?: string | null
}

export type Ticket = {
  ticketId: number
  vehicleId: number
  damageSeverity: string
  damageType: string
  recommendedAction?: string
  estimatedDurationHours: number
  status: string
  recordId?: number | null
  bookingId?: number | null
  tripId?: number | null
  openedByEventType?: string | null
  createdAt?: string | null
  bookingCode?: string | null
  userId?: string | null
  customerName?: string | null
  vehicleName?: string | null
  stationName?: string | null
  stationAddress?: string | null
  zone?: string | null
  recordSummary?: string | null
  evidenceCount?: number
  hasEvidence?: boolean
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
  evidenceUrls?: string[]
  detectedDamage: string[]
  createdAt?: string | null
  updatedAt?: string | null
  bookingCode?: string | null
  userId?: string | null
  customerName?: string | null
  vehicleName?: string | null
  stationName?: string | null
  stationAddress?: string | null
  zone?: string | null
  evidenceCount?: number
  hasEvidence?: boolean
}

export type TripDisruptionAdvisory = {
  notificationId: number
  createdAt?: string | null
  bookingId?: number | null
  tripId?: number | null
  vehicleId?: number | null
  vehicleName: string
  severity: string
  subject: string
  message: string
  requiresImmediateEndTrip: boolean
  endReason: string
}

export type SearchResponse = {
  vehicleList: Vehicle[]
  estimatedPrice: number
  availabilitySummary: string
  selectedStationId?: string
  mapCenter?: MapCenter
  stationList: SearchStation[]
}

export type DiscoveryMetadata = {
  vehicles: Vehicle[]
  filters: VehicleFilters
}

export type CustomerHomeResponse = {
  customerSummary: CustomerSummary
  bookings: Booking[]
  notifications: Notification[]
}

export type BookingListResponse = {
  customerSummary: CustomerSummary
  bookings: Booking[]
}

export type BookingDetailResponse = {
  booking: Booking
  vehicle: Vehicle
  customerSummary: CustomerSummary
}

export type CustomerWalletResponse = {
  customerSummary: CustomerSummary
  bookings: Booking[]
  payments: Payment[]
  ledgerEntries: WalletLedgerEntry[]
}

export type CustomerAccountResponse = {
  customerSummary: CustomerSummary
  notifications: Notification[]
}

export type RentalExecutionStatusResponse = {
  bookings: Booking[]
  trips: Trip[]
  vehicles: Vehicle[]
  records: RecordItem[]
  notifications: Notification[]
  liveTripAdvisory?: TripDisruptionAdvisory | null
}

export type OpsDashboardResponse = {
  vehicles: Vehicle[]
  customers: CustomerSummary[]
  bookings: Booking[]
  trips: Trip[]
  tickets: Ticket[]
  records: RecordItem[]
  reviewQueue: RecordItem[]
  payments: Payment[]
  notifications: Notification[]
}

export type OpsIncidentsResponse = {
  tickets: Ticket[]
  records: RecordItem[]
  reviewQueue: RecordItem[]
}

export type OpsBillingResponse = {
  customers: CustomerSummary[]
  bookings: Booking[]
  trips: Trip[]
  payments: Payment[]
}

export type OpsInboxResponse = {
  notifications: Notification[]
}

export type OpsTicketDetailResponse = {
  ticket: Ticket
  vehicle?: Vehicle | null
  customer?: CustomerSummary | null
  booking?: Booking | null
  trip?: Trip | null
  record?: RecordItem | null
  evidenceUrls: string[]
}

export type WalletSettlement = {
  cashRefundAmount: number
  restoredIncludedHours: number
  discountAmount: number
  reconciliationStatus: string
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
  reviewState: string
  bookingStatus?: string | null
  bookingCancelled: boolean
  resolutionCompleted: boolean
  booking?: Booking | null
  vehicle?: Vehicle | null
  walletSettlement: WalletSettlement
  maintenanceTicketId?: number | null
}

export type InspectionCancellationResult = {
  bookingId: number
  vehicleId: number
  recordId: number
  assessmentResult: {
    severity: string
    confidence: number
    detectedDamage: string[]
  }
  tripStatus: 'BLOCKED'
  warningMessage: string
  manualReview: boolean
  reviewState: string
  status: string
  message: string
  bookingStatus?: string | null
  bookingCancelled: boolean
  resolutionCompleted: boolean
  booking?: Booking | null
  vehicle?: Vehicle | null
  walletSettlement: WalletSettlement
  maintenanceTicketId?: number | null
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
  renewalReconciliationPending?: boolean
  discountAmount: number
  allowanceHoursApplied: number
  allowanceHoursRestored?: number
  customerSummary: CustomerSummary
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

function parseDateOnly(value: string) {
  const match = DATE_ONLY_PATTERN.exec(value)
  if (!match) return null
  return new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12))
}

const OPS_API_KEY = import.meta.env.VITE_OPS_API_KEY ?? 'ops-demo-key-fleetshare'

export function opsFetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  return fetchJson<T>(path, {
    ...options,
    headers: {
      ...options?.headers,
      'X-Mechanic-Key': OPS_API_KEY,
    },
  })
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

export function formatSeverityLabel(value?: string | null) {
  if (!value) return 'N/A'
  return value.replaceAll('_', ' ')
}

export function formatDateOnly(value?: string | null) {
  if (!value) return 'N/A'
  const parsedDate = parseDateOnly(value)
  if (!parsedDate) return formatDate(value)
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: BILLING_TIMEZONE,
  }).format(parsedDate)
}

export function formatDate(value?: string | null) {
  if (!value) return 'N/A'
  const parsedDate = parseDateOnly(value)
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: parsedDate ? BILLING_TIMEZONE : undefined,
  }).format(parsedDate ?? new Date(value))
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
  const parsedDate = parseDateOnly(value)
  return new Intl.DateTimeFormat(undefined, {
    day: 'numeric',
    month: 'short',
    timeZone: parsedDate ? BILLING_TIMEZONE : undefined,
  }).format(parsedDate ?? new Date(value))
}