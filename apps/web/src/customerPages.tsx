import { type Dispatch, type ReactNode, type SetStateAction, useEffect, useState } from 'react'
import { Link, NavLink, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import {
  fetchJson,
  formatDateOnly,
  formatDateTime,
  formatHours,
  formatMoney,
  formatSeverityLabel,
} from './appTypes'
import type {
  Booking,
  CustomerSummary,
  EndTripResult,
  InspectionSubmissionResult,
  InternalDamageResult,
  Notification,
  Payment,
  PostTripInspectionResult,
  RecordItem,
  Trip,
  Vehicle,
  VehicleFilters,
} from './appTypes'

export function LandingPage({
  customers,
  onSelectCustomer,
  busy,
  status,
}: {
  customers: CustomerSummary[]
  onSelectCustomer: (userId: string) => void
  busy: boolean
  status: string
}) {
  const navigate = useNavigate()

  return (
    <div className="marketing-shell">
      <section className="marketing-hero">
        <div className="marketing-copy">
          <p className="eyebrow">FleetShare Customer Demo</p>
          <h1>Choose a demo driver and step through a real car-sharing journey.</h1>
          <p className="marketing-lead">
            Search by pick-up and return location, see subscription-aware pricing, confirm a booking, complete a pre-trip inspection, and watch allowance usage move after the trip.
          </p>
          <div className="status-pill">{busy ? 'Syncing demo data...' : status}</div>
        </div>
        <div className="marketing-card">
          <p className="mini-label">What this demo shows</p>
          <ul className="feature-list">
            <li>Allowance-aware vehicle search</li>
            <li>Overnight billing-cycle rollover with provisional charges</li>
            <li>Trip, payments, and notification lifecycle</li>
          </ul>
        </div>
      </section>

      <section className="profile-grid">
        {customers.map((customer) => (
          <article className="profile-card" key={customer.userId}>
            <div className="profile-card__top">
              <p className="mini-label">{customer.demoBadge || 'Demo customer'}</p>
              <h2>{customer.displayName}</h2>
              <p>{customer.planName.replaceAll('_', ' ')}</p>
            </div>
            <div className="profile-metrics">
              <div>
                <span>Remaining</span>
                <strong>{formatHours(customer.remainingHoursThisCycle)}</strong>
              </div>
              <div>
                <span>Used</span>
                <strong>{formatHours(customer.hoursUsedThisCycle)}</strong>
              </div>
              <div>
                <span>Renewal</span>
                <strong>{formatDateOnly(customer.subscriptionEndDate)}</strong>
              </div>
            </div>
            <button
              className="primary wide-button"
              onClick={() => {
                onSelectCustomer(customer.userId)
                navigate('/app/home')
              }}
              type="button"
            >
              Enter as {customer.displayName.split(' ')[0]}
            </button>
          </article>
        ))}
      </section>

      <footer className="marketing-footer">
        <Link to="/ops">Open hidden ops console</Link>
      </footer>
    </div>
  )
}

export function CustomerShell({
  activeUser,
  busy,
  status,
  onSwitchUser,
  children,
}: {
  activeUser: CustomerSummary | null
  busy: boolean
  status: string
  onSwitchUser: () => void
  children: ReactNode
}) {
  return (
    <div className="app-shell">
      <header className="app-topbar">
        <Link className="brand-lockup" to="/app/home">
          <span className="brand-mark">F</span>
          <div>
            <strong>FleetShare</strong>
            <small>Customer app demo</small>
          </div>
        </Link>
        <nav className="customer-nav">
          <NavLink to="/app/home">Home</NavLink>
          <NavLink to="/app/discover">Discover</NavLink>
          <NavLink to="/app/trips">Trips</NavLink>
          <NavLink to="/app/account">Account</NavLink>
        </nav>
        <div className="topbar-actions">
          <div className="customer-chip">
            <span>{activeUser?.displayName ?? 'No customer'}</span>
            <small>{activeUser?.planName.replaceAll('_', ' ')}</small>
          </div>
          <button onClick={onSwitchUser} type="button">
            Switch user
          </button>
        </div>
      </header>
      <div className="banner-row">
        <div className={`status-banner ${busy ? 'status-banner--busy' : ''}`}>{busy ? 'Updating...' : status}</div>
      </div>
      <main className="customer-page">{children}</main>
    </div>
  )
}

export function HomePage({
  customerSummary,
  notifications,
  upcomingBookings,
  activeTrip,
}: {
  customerSummary: CustomerSummary | null
  notifications: Notification[]
  upcomingBookings: Booking[]
  activeTrip: Trip | null
}) {
  const nextBooking = upcomingBookings[0] ?? null

  return (
    <div className="stack">
      <section className="customer-hero">
        <div>
          <p className="eyebrow">Subscription overview</p>
          <h1>{customerSummary ? `${formatHours(customerSummary.remainingHoursThisCycle)} left this cycle` : 'Loading subscription'}</h1>
          <p className="hero-copy">
            Your monthly allowance is tracked by the pricing service. Discover shows how much of the trip fits within your remaining hours before any extra billing starts.
          </p>
        </div>
        <div className="summary-panel">
          <div>
            <span>Plan</span>
            <strong>{customerSummary?.planName.replaceAll('_', ' ') ?? '...'}</strong>
          </div>
          <div>
            <span>Used this cycle</span>
            <strong>{customerSummary ? formatHours(customerSummary.hoursUsedThisCycle) : '...'}</strong>
          </div>
          <div>
            <span>Subscription ends on</span>
            <strong>{customerSummary ? formatDateOnly(customerSummary.subscriptionEndDate) : '...'}</strong>
          </div>
        </div>
      </section>

      <section className="dashboard-grid">
        <article className="panel-card">
          <div className="panel-card__header">
            <div>
              <p className="mini-label">Next up</p>
              <h2>{activeTrip ? 'Active trip in progress' : 'Upcoming booking'}</h2>
            </div>
            <Link to="/app/trips">Open trip hub</Link>
          </div>
          {activeTrip ? (
            <div className="timeline-card">
              <strong>Trip #{activeTrip.tripId}</strong>
              <p>Started {formatDateTime(activeTrip.startedAt)}</p>
              <p>Vehicle #{activeTrip.vehicleId}</p>
            </div>
          ) : nextBooking ? (
            <div className="timeline-card">
              <strong>Booking #{nextBooking.bookingId}</strong>
              <p>{formatDateTime(nextBooking.startTime)} to {formatDateTime(nextBooking.endTime)}</p>
              <p>{nextBooking.pickupLocation} pick-up & return</p>
            </div>
          ) : (
            <div className="empty-card">
              <p>No upcoming booking yet.</p>
              <Link to="/app/discover">Find a vehicle</Link>
            </div>
          )}
        </article>

        <article className="panel-card">
          <div className="panel-card__header">
            <div>
              <p className="mini-label">Inbox</p>
              <h2>Latest notifications</h2>
            </div>
            <Link to="/app/account">See all</Link>
          </div>
          <div className="notification-stack">
            {notifications.slice(0, 3).map((notification) => (
              <div className="notification-card" key={notification.notificationId}>
                <strong>{notification.subject}</strong>
                <p>{notification.message}</p>
              </div>
            ))}
            {notifications.length === 0 ? <div className="empty-card"><p>No notifications yet.</p></div> : null}
          </div>
        </article>
      </section>
    </div>
  )
}

export function DiscoverPage({
  customerSummary,
  deferredSearchResults,
  searchForm,
  searchSummary,
  vehicleFilters,
  onReserve,
  onSearch,
  setSearchForm,
}: {
  customerSummary: CustomerSummary | null
  deferredSearchResults: Vehicle[]
  searchForm: { pickupLocation: string; vehicleType: string; startTime: string; endTime: string }
  searchSummary: string
  vehicleFilters: VehicleFilters
  onReserve: (vehicleId: number) => void
  onSearch: () => Promise<void>
  setSearchForm: Dispatch<SetStateAction<{ pickupLocation: string; vehicleType: string; startTime: string; endTime: string }>>
}) {
  const navigate = useNavigate()

  return (
    <div className="stack">
      <section className="discover-hero">
        <div>
          <p className="eyebrow">Discover vehicles</p>
          <h1>Book around your allowance, not around raw hourly rates.</h1>
          <p className="hero-copy">
            {customerSummary
              ? `${customerSummary.displayName} has ${formatHours(customerSummary.remainingHoursThisCycle)} remaining this cycle at ${formatMoney(customerSummary.hourlyRate)}/hour beyond included usage.`
              : 'Loading customer summary.'}
          </p>
        </div>
      </section>

      <section className="panel-card">
        <div className="panel-card__header">
          <div>
            <p className="mini-label">Trip planner</p>
            <h2>Choose your pick-up & return location</h2>
          </div>
        </div>
        <div className="form-grid customer-form-grid">
          <label>
            Pick-up & Return Location
            <select value={searchForm.pickupLocation} onChange={(event) => setSearchForm((current) => ({ ...current, pickupLocation: event.target.value }))}>
              {vehicleFilters.locations.map((location) => (
                <option key={location} value={location}>
                  {location}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vehicle Type
            <select value={searchForm.vehicleType} onChange={(event) => setSearchForm((current) => ({ ...current, vehicleType: event.target.value }))}>
              {vehicleFilters.vehicleTypes.map((vehicleType) => (
                <option key={vehicleType} value={vehicleType}>
                  {vehicleType}
                </option>
              ))}
            </select>
          </label>
          <label>
            Start time
            <input type="datetime-local" value={searchForm.startTime} onChange={(event) => setSearchForm((current) => ({ ...current, startTime: event.target.value }))} />
          </label>
          <label>
            End time
            <input type="datetime-local" value={searchForm.endTime} onChange={(event) => setSearchForm((current) => ({ ...current, endTime: event.target.value }))} />
          </label>
        </div>
        <button className="primary" onClick={() => void onSearch()} type="button">
          Search available cars
        </button>
      </section>

      <section className="results-section">
        <div className="section-heading">
          <div>
            <p className="mini-label">Search results</p>
            <h2>{searchSummary || 'No search run yet'}</h2>
          </div>
        </div>
        <div className="results-grid">
          {deferredSearchResults.map((vehicle) => (
            <article className="result-card" key={vehicle.vehicleId ?? vehicle.id}>
              <div className="result-card__top">
                <div>
                  <p className="mini-label">{vehicle.vehicleType}</p>
                  <h3>{vehicle.model}</h3>
                  <p>{vehicle.plateNumber} · {vehicle.zone}</p>
                </div>
                <span className="status-tag">{vehicle.status}</span>
              </div>
              <div className="quote-grid">
                <div>
                  <span>Estimated due now</span>
                  <strong>{formatMoney(vehicle.estimatedPrice ?? 0)}</strong>
                </div>
                <div>
                  <span>Allowance applied</span>
                  <strong>{formatHours(vehicle.includedHoursApplied ?? 0)}</strong>
                </div>
                <div>
                  <span>Allowance after trip</span>
                  <strong>{formatHours(vehicle.includedHoursRemainingAfter ?? 0)}</strong>
                </div>
                <div>
                  <span>Extra billed hours</span>
                  <strong>{formatHours(vehicle.billableHours ?? 0)}</strong>
                </div>
              </div>
              {vehicle.provisionalPostMidnightHours ? (
                <div className="notice-card">
                  <strong>Renewal boundary detected</strong>
                  <p>
                    {formatHours(vehicle.provisionalPostMidnightHours)} will be charged provisionally now and may be re-rated after the subscription ends on {formatDateOnly(vehicle.subscriptionEndDate)}.
                  </p>
                </div>
              ) : null}
              <div className="result-card__footer">
                <p>{vehicle.allowanceStatus}</p>
                <button
                  className="primary"
                  onClick={() => {
                    onReserve(vehicle.vehicleId ?? vehicle.id)
                    navigate('/app/bookings/processing')
                  }}
                  type="button"
                >
                  Reserve this car
                </button>
              </div>
            </article>
          ))}
          {deferredSearchResults.length === 0 ? (
            <div className="empty-card wide-empty">
              <p>Run a search to see customer-facing vehicle cards and subscription-aware pricing.</p>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  )
}

export function BookingProcessingPage({
  pendingBooking,
  vehicles,
}: {
  pendingBooking: {
    status: 'processing' | 'success' | 'error'
    vehicleId: number
    bookingId?: number
    error?: string
  } | null
  vehicles: Vehicle[]
}) {
  const navigate = useNavigate()
  const vehicle = vehicles.find((item) => item.id === pendingBooking?.vehicleId) ?? null

  useEffect(() => {
    if (pendingBooking?.status !== 'success' || !pendingBooking.bookingId) {
      return
    }
    const timer = window.setTimeout(() => {
      navigate(`/app/bookings/${pendingBooking.bookingId}`, { replace: true })
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [navigate, pendingBooking])

  if (!pendingBooking) {
    return (
      <section className="panel-card">
        <h2>No booking in progress</h2>
        <p>Start from Discover to reserve a vehicle.</p>
        <Link className="primary link-button" to="/app/discover">
          Back to discover
        </Link>
      </section>
    )
  }

  return (
    <section className="processing-shell">
      <div className="processing-card">
        <p className="eyebrow">Reservation in progress</p>
        <h1>
          {pendingBooking.status === 'processing'
            ? 'Confirming your booking...'
            : pendingBooking.status === 'success'
              ? `Booking #${pendingBooking.bookingId} confirmed.`
              : 'We could not confirm this booking.'}
        </h1>
        <p className="hero-copy">
          {pendingBooking.status === 'processing'
            ? `We are reserving ${vehicle?.model ?? `vehicle #${pendingBooking.vehicleId}`}, checking payment, and saving the booking record.`
            : pendingBooking.status === 'success'
              ? 'Your reservation is secured. Redirecting to the booking confirmation screen now.'
              : pendingBooking.error ?? 'Please return to discover and try again.'}
        </p>
        <div className="processing-steps">
          <div className={`processing-step ${pendingBooking.status !== 'error' ? 'processing-step--done' : ''}`}>
            <strong>1. Reserve vehicle slot</strong>
            <span>{pendingBooking.status === 'error' ? 'Attempted' : 'Completed'}</span>
          </div>
          <div className={`processing-step ${pendingBooking.status === 'processing' ? 'processing-step--active' : pendingBooking.status === 'success' ? 'processing-step--done' : ''}`}>
            <strong>2. Price and confirm booking</strong>
            <span>
              {pendingBooking.status === 'processing'
                ? 'In progress'
                : pendingBooking.status === 'success'
                  ? 'Completed'
                  : 'Failed'}
            </span>
          </div>
          <div className={`processing-step ${pendingBooking.status === 'success' ? 'processing-step--done' : ''}`}>
            <strong>3. Open confirmation details</strong>
            <span>{pendingBooking.status === 'success' ? 'Next' : 'Waiting'}</span>
          </div>
        </div>
        {pendingBooking.status === 'processing' ? <div className="processing-spinner" aria-hidden="true" /> : null}
        <div className="button-strip">
          {pendingBooking.status === 'success' && pendingBooking.bookingId ? (
            <Link className="primary link-button" to={`/app/bookings/${pendingBooking.bookingId}`}>
              Open booking details
            </Link>
          ) : null}
          {pendingBooking.status === 'error' ? (
            <Link className="primary link-button" to="/app/discover">
              Back to discover
            </Link>
          ) : null}
        </div>
      </div>
    </section>
  )
}

export function BookingDetailsPage({
  bookings,
  customerSummary,
  notifications,
  payments,
  trips,
  vehicles,
}: {
  bookings: Booking[]
  customerSummary: CustomerSummary | null
  notifications: Notification[]
  payments: Payment[]
  trips: Trip[]
  vehicles: Vehicle[]
}) {
  const { bookingId } = useParams()
  const [fallbackBooking, setFallbackBooking] = useState<Booking | null>(null)
  const [fallbackVehicle, setFallbackVehicle] = useState<Vehicle | null>(null)
  const [loadingFallback, setLoadingFallback] = useState(false)

  useEffect(() => {
    if (!bookingId) {
      setFallbackBooking(null)
      setFallbackVehicle(null)
      setLoadingFallback(false)
      return
    }
    if (bookings.some((item) => String(item.bookingId) === bookingId)) {
      setFallbackBooking(null)
      setFallbackVehicle(null)
      setLoadingFallback(false)
      return
    }

    let cancelled = false
    setLoadingFallback(true)
    void fetchJson<{ booking: Booking; vehicle: Vehicle }>(`/process-booking/bookings/${bookingId}`)
      .then((detail) => {
        if (cancelled) {
          return
        }
        setFallbackBooking(detail.booking)
        setFallbackVehicle(detail.vehicle)
      })
      .catch(() => {
        if (cancelled) {
          return
        }
        setFallbackBooking(null)
        setFallbackVehicle(null)
      })
      .finally(() => {
        if (!cancelled) {
          setLoadingFallback(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [bookingId, bookings])

  const booking = bookings.find((item) => String(item.bookingId) === bookingId) ?? fallbackBooking
  const vehicle = vehicles.find((item) => item.id === booking?.vehicleId) ?? fallbackVehicle
  const pricing = booking?.pricingSnapshot
  const trip = booking ? trips.find((item) => item.bookingId === booking.bookingId) ?? null : null
  const relatedPayments = booking ? payments.filter((item) => item.bookingId === booking.bookingId) : []
  const refundPayment = relatedPayments.find((item) => item.status === 'REFUNDED') ?? null
  const apologyCreditPayment = relatedPayments.find((item) => item.status === 'ADJUSTED') ?? null
  const disruptionReason = trip?.disruptionReason ?? refundPayment?.reason ?? apologyCreditPayment?.reason ?? null
  const disruptionNotification = booking
    ? notifications.find((item) => item.bookingId === booking.bookingId && /disruption|issue|compensation|refund|cancelled/i.test(`${item.subject} ${item.message}`)) ?? null
    : null
  const disruptedBooking = booking?.status === 'DISRUPTED' || Boolean(disruptionReason)

  if (!booking && loadingFallback) {
    return (
      <section className="panel-card">
        <h2>Loading booking details</h2>
        <p>We are loading the confirmed booking now.</p>
      </section>
    )
  }

  if (!booking) {
    return (
      <section className="panel-card">
        <h2>Booking not found</h2>
        <p>The booking may not have been created yet in this session.</p>
      </section>
    )
  }

  return (
    <div className="stack">
      <section className="booking-hero">
        <div>
          <p className="eyebrow">{disruptedBooking ? 'Disrupted booking' : booking.tripId ? 'Past booking' : 'Booking confirmed'}</p>
          <h1>{disruptedBooking ? `Booking #${booking.bookingId} ended early.` : `Reservation #${booking.bookingId} is ready for the next step.`}</h1>
          <p className="hero-copy">
            {disruptedBooking
              ? disruptionNotification?.message ?? `FleetShare marked this booking as disrupted because of ${titleCaseWords(disruptionReason ?? 'trip disruption')}.`
              : 'Your booking is stored in the booking service while the pricing snapshot below shows exactly how allowance and provisional renewal charges were calculated at reservation time.'}
          </p>
        </div>
        <div className="summary-panel">
          <div>
            <span>{disruptedBooking ? 'Final fare' : 'Due now'}</span>
            <strong>{formatMoney(disruptedBooking ? booking.finalPrice : booking.displayedPrice)}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>{booking.status}</strong>
          </div>
          <div>
            <span>Subscription ends on</span>
            <strong>{customerSummary ? formatDateOnly(customerSummary.subscriptionEndDate) : 'N/A'}</strong>
          </div>
        </div>
      </section>

      <section className="dashboard-grid">
        <article className="panel-card">
          <p className="mini-label">Vehicle</p>
          <h2>{vehicle?.model ?? `Vehicle #${booking.vehicleId}`}</h2>
          <p>{vehicle?.plateNumber ?? ''}</p>
          <p>{booking.pickupLocation} pick-up & return</p>
          <p>{formatDateTime(booking.startTime)} to {formatDateTime(booking.endTime)}</p>
        </article>

        {disruptedBooking ? (
          <article className="panel-card">
            <p className="mini-label">Disruption outcome</p>
            <h2>Refund and credit status</h2>
            <div className="quote-grid">
              <div>
                <span>End reason</span>
                <strong>{titleCaseWords(disruptionReason ?? 'Trip disruption')}</strong>
              </div>
              <div>
                <span>Cash refund</span>
                <strong>{refundPayment ? formatMoney(refundPayment.amount) : 'Queued'}</strong>
              </div>
              <div>
                <span>Apology credit</span>
                <strong>{apologyCreditPayment ? formatMoney(apologyCreditPayment.amount) : 'Queued'}</strong>
              </div>
              <div>
                <span>Compensation status</span>
                <strong>{refundPayment || apologyCreditPayment ? 'Recorded' : 'Queued'}</strong>
              </div>
            </div>
          </article>
        ) : null}

        <article className="panel-card">
          <p className="mini-label">Pricing snapshot</p>
          <h2>Allowance impact</h2>
          <div className="quote-grid">
            <div>
              <span>Trip duration</span>
              <strong>{formatHours(pricing?.totalHours ?? 0)}</strong>
            </div>
            <div>
              <span>Included now</span>
              <strong>{formatHours(pricing?.includedHoursApplied ?? 0)}</strong>
            </div>
            <div>
              <span>Remaining after booking</span>
              <strong>{formatHours(pricing?.includedHoursRemainingAfter ?? 0)}</strong>
            </div>
            <div>
              <span>Extra billed hours</span>
              <strong>{formatHours(pricing?.billableHours ?? 0)}</strong>
            </div>
          </div>
          {pricing?.provisionalPostMidnightHours ? (
            <div className="notice-card">
              <strong>Provisional overnight charge</strong>
              <p>
                {formatHours(pricing.provisionalPostMidnightHours)} after midnight is provisionally charged now at {formatMoney(pricing.hourlyRate)}/hour. Renewal reconciliation may refund part of it later.
              </p>
            </div>
          ) : null}
        </article>
      </section>

      <div className="button-strip">
        <Link className="primary link-button" to="/app/trips">
          Continue to trip hub
        </Link>
        <Link className="ghost-link" to="/app/discover">
          Find another vehicle
        </Link>
      </div>
    </div>
  )
}

function titleCaseWords(value: string) {
  return value
    .toLowerCase()
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function TripsPage({
  activeTrip,
  bookings,
  completedTrips,
  latestInspectionResult,
  onCancelModerateDamage,
  onStartTrip,
  onSubmitInspection,
  upcomingBookings,
  vehicles,
  records,
}: {
  activeTrip: Trip | null
  bookings: Booking[]
  completedTrips: Trip[]
  latestInspectionResult: InspectionSubmissionResult | null
  onCancelModerateDamage: (bookingId: number, vehicleId: number) => Promise<void>
  onStartTrip: (bookingId: number, vehicleId: number, notes: string) => Promise<void>
  onSubmitInspection: (bookingId: number, vehicleId: number, notes: string, photo: File | null) => Promise<void>
  upcomingBookings: Booking[]
  vehicles: Vehicle[]
  records: RecordItem[]
}) {
  const nextBooking = upcomingBookings[0] ?? null
  const nextVehicle = vehicles.find((vehicle) => vehicle.id === nextBooking?.vehicleId) ?? null
  const inspectionRecord = nextBooking
    ? records.find((record) => record.bookingId === nextBooking.bookingId && record.recordType === 'EXTERNAL_DAMAGE') ?? null
    : null
  const inspectionFeedback = nextBooking && latestInspectionResult?.bookingId === nextBooking.bookingId ? latestInspectionResult : null
  const inspectionCleared = Boolean(inspectionRecord && inspectionRecord.reviewState === 'EXTERNAL_ASSESSED' && inspectionRecord.severity !== 'SEVERE')
  const inspectionSeverity = inspectionFeedback?.assessmentResult.severity ?? inspectionRecord?.severity ?? 'PENDING'
  const moderateInspection = Boolean(inspectionRecord && inspectionRecord.reviewState === 'EXTERNAL_ASSESSED' && inspectionSeverity === 'MODERATE')
  const [inspectionNotes, setInspectionNotes] = useState('Vehicle exterior looks clean.')
  const [inspectionPhoto, setInspectionPhoto] = useState<File | null>(null)
  const [startNotes, setStartNotes] = useState('')

  return (
    <div className="stack">
      <section className="dashboard-grid">
        <article className="panel-card">
          <div className="panel-card__header">
            <div>
              <p className="mini-label">Pre-trip</p>
              <h2>Upcoming booking</h2>
            </div>
          </div>
          {nextBooking ? (
            <>
              <p><strong>{nextVehicle?.model ?? `Vehicle #${nextBooking.vehicleId}`}</strong></p>
              <p>{formatDateTime(nextBooking.startTime)} to {formatDateTime(nextBooking.endTime)}</p>
              <p>{nextBooking.pickupLocation} pick-up & return</p>
              <label>
                Inspection notes
                <textarea rows={3} value={inspectionNotes} onChange={(event) => setInspectionNotes(event.target.value)} />
              </label>
              <label>
                Optional photo
                <input type="file" accept="image/*" onChange={(event) => setInspectionPhoto(event.target.files?.[0] ?? null)} />
              </label>
              <div className="notice-card">
                <strong>Inspection gate</strong>
                <p>
                  {inspectionCleared
                    ? moderateInspection
                      ? 'Moderate external damage was noted. You can still click Unlock vehicle, or cancel the booking to escalate the incident to ops.'
                      : 'Inspection cleared. Click Unlock vehicle to send the unlock command and start the trip.'
                    : inspectionRecord
                      ? `Inspection status: ${inspectionRecord.reviewState}. Unlock stays disabled until the external inspection is cleared.`
                      : 'Submit the external inspection first. Start trip stays locked until that record is created and cleared.'}
                </p>
              </div>
              {inspectionRecord ? (
                <div className={`notice-card ${inspectionCleared ? 'notice-card--success' : inspectionRecord.reviewState === 'MANUAL_REVIEW' || inspectionRecord.reviewState === 'EXTERNAL_BLOCKED' ? 'notice-card--error' : ''}`}>
                  <strong>Latest inspection result</strong>
                  <p>
                    Severity: {formatSeverityLabel(inspectionSeverity)}. Review state: {inspectionRecord.reviewState}.
                  </p>
                  <p>
                    {inspectionCleared
                      ? moderateInspection
                        ? 'Trip start is still allowed. If the customer is uncomfortable proceeding, they can cancel here and the same damage incident workflow will notify ops and process compensation.'
                        : 'No trip has started yet. The user must still click Unlock vehicle.'
                      : inspectionRecord.reviewState === 'MANUAL_REVIEW'
                        ? 'The inspection is waiting for manual review, so unlock is blocked.'
                        : inspectionRecord.reviewState === 'EXTERNAL_BLOCKED'
                          ? 'Damage was flagged as blocking, so unlock is blocked.'
                          : inspectionFeedback?.warningMessage ?? 'Inspection data is still being processed.'}
                  </p>
                </div>
              ) : null}
              <div className="button-strip">
                <button className="primary" onClick={() => void onSubmitInspection(nextBooking.bookingId, nextBooking.vehicleId, inspectionNotes, inspectionPhoto)} type="button">
                  Submit inspection
                </button>
                <button className={inspectionCleared ? 'primary' : ''} disabled={!inspectionCleared} onClick={() => void onStartTrip(nextBooking.bookingId, nextBooking.vehicleId, startNotes)} type="button">
                  Unlock vehicle
                </button>
                {moderateInspection ? (
                  <button onClick={() => void onCancelModerateDamage(nextBooking.bookingId, nextBooking.vehicleId)} type="button">
                    Cancel due to damage
                  </button>
                ) : null}
              </div>
              <label>
                Start notes
                <input value={startNotes} onChange={(event) => setStartNotes(event.target.value)} placeholder="Optional notes sent with the unlock/start request" />
              </label>
            </>
          ) : activeTrip ? (
            <div className="notice-card notice-card--success">
              <strong>Current booking is already in progress</strong>
              <p>Booking #{activeTrip.bookingId} has already moved into the live trip flow</p>
            </div>
          ) : (
            <div className="empty-card"><p>No upcoming bookings. Reserve a car first.</p></div>
          )}
        </article>

        <article className="panel-card">
          <div className="panel-card__header">
            <div>
              <p className="mini-label">Live trip</p>
              <h2>Active trip control</h2>
            </div>
          </div>
          {activeTrip ? (
            <>
              <p><strong>Trip #{activeTrip.tripId}</strong></p>
              <p>Vehicle unlocked and trip started {formatDateTime(activeTrip.startedAt)}</p>
              <p>Use the fault report flow if the car develops an issue during the trip, or start the normal end-trip flow when you are ready to return it.</p>
              <div className="button-strip">
                <Link className="primary link-button" to="/app/trips/end-inspection?reason=USER_COMPLETED">
                  End trip
                </Link>
                <Link className="ghost-link" to="/app/trips/report-problem">
                  Report vehicle problem
                </Link>
              </div>
            </>
          ) : (
            <div className="empty-card"><p>No active trip yet. A cleared inspection alone does not start the trip; the user must click Unlock vehicle.</p></div>
          )}
        </article>
      </section>

      <section className="panel-card">
        <div className="panel-card__header">
          <div>
            <p className="mini-label">History</p>
            <h2>Completed trips</h2>
          </div>
        </div>
        <div className="history-list">
          {completedTrips.map((trip) => {
            const booking = bookings.find((item) => item.bookingId === trip.bookingId)
            return (
              <article className="history-card" key={trip.tripId}>
                <div>
                  <strong>Trip #{trip.tripId}</strong>
                  <p>{formatDateTime(trip.startedAt)} to {formatDateTime(trip.endedAt)}</p>
                </div>
                <div>
                  <span>Duration</span>
                  <strong>{formatHours(trip.durationHours)}</strong>
                </div>
                <div>
                  <span>Final fare</span>
                  <strong>{formatMoney(booking?.finalPrice ?? booking?.displayedPrice ?? 0)}</strong>
                </div>
              </article>
            )
          })}
          {completedTrips.length === 0 ? <div className="empty-card"><p>No completed trips yet.</p></div> : null}
        </div>
      </section>
    </div>
  )
}

export function TripProblemPage({
  activeTrip,
  onSubmitProblem,
}: {
  activeTrip: Trip | null
  onSubmitProblem: (notes: string) => Promise<InternalDamageResult>
}) {
  const navigate = useNavigate()
  const [notes, setNotes] = useState('Dashboard warning light came on while driving.')

  if (!activeTrip) {
    return (
      <section className="panel-card">
        <h2>No active trip</h2>
        <p>You can only report a vehicle problem while a trip is active.</p>
        <Link className="primary link-button" to="/app/trips">
          Back to trip hub
        </Link>
      </section>
    )
  }

  return (
    <section className="panel-card">
      <p className="eyebrow">Active trip problem report</p>
      <h1>Tell FleetShare what is happening with the car.</h1>
      <p className="hero-copy">
        Submit a short description of the fault. FleetShare will assess the issue against the latest telemetry and tell you whether to stop and end the trip.
      </p>
      <label>
        Problem description
        <textarea rows={5} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <div className="button-strip">
        <button
          className="primary"
          disabled={!notes.trim()}
          onClick={() => {
            void onSubmitProblem(notes).then(() => navigate('/app/trips/problem-advisory'))
          }}
          type="button"
        >
          Submit problem
        </button>
        <Link className="ghost-link" to="/app/trips">
          Back
        </Link>
      </div>
    </section>
  )
}

export function TripProblemResultPage({
  activeTrip,
  reportedProblem,
}: {
  activeTrip: Trip | null
  reportedProblem: InternalDamageResult | null
}) {
  if (!reportedProblem) {
    return (
      <section className="panel-card">
        <h2>No problem report found</h2>
        <p>Start from the active trip page to submit a vehicle problem.</p>
        <Link className="primary link-button" to="/app/trips">
          Back to trip hub
        </Link>
      </section>
    )
  }

  return (
    <section className="panel-card">
      <p className="eyebrow">Problem assessment</p>
      <h1>{reportedProblem.blocked ? 'Stop safely and end the trip.' : 'The report has been recorded.'}</h1>
      <div className={`notice-card ${reportedProblem.blocked ? 'notice-card--error' : 'notice-card--success'}`}>
        <strong>Severity: {formatSeverityLabel(reportedProblem.severity)}</strong>
        <p>{reportedProblem.recommendedAction}</p>
        {reportedProblem.duplicateSuppressed ? <p>FleetShare detected an existing matching incident and avoided repeating the downstream recovery cycle.</p> : null}
      </div>
      <div className="button-strip">
        {reportedProblem.blocked && activeTrip ? (
          <Link className="primary link-button" to="/app/trips/end-inspection?reason=SEVERE_INTERNAL_FAULT">
            Continue to end trip
          </Link>
        ) : (
          <Link className="primary link-button" to="/app/trips">
            Return to trip hub
          </Link>
        )}
      </div>
    </section>
  )
}

export function EndTripInspectionPage({
  activeTrip,
  onSubmitInspection,
  vehicles,
}: {
  activeTrip: Trip | null
  onSubmitInspection: (notes: string, photo: File | null) => Promise<PostTripInspectionResult>
  vehicles: Vehicle[]
}) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [notes, setNotes] = useState('Vehicle returned in good condition.')
  const [photo, setPhoto] = useState<File | null>(null)
  const endReason = searchParams.get('reason') ?? 'USER_COMPLETED'
  const vehicle = vehicles.find((item) => item.id === activeTrip?.vehicleId) ?? null

  if (!activeTrip) {
    return (
      <section className="panel-card">
        <h2>No active trip</h2>
        <p>The end-trip wizard starts from an active trip.</p>
        <Link className="primary link-button" to="/app/trips">
          Back to trip hub
        </Link>
      </section>
    )
  }

  return (
    <section className="panel-card">
      <p className="eyebrow">End trip step 1 of 3</p>
      <h1>Complete the mandatory post-trip inspection.</h1>
      <p className="hero-copy">
        Record the exterior condition after use before you confirm the lock command for {vehicle?.model ?? `vehicle #${activeTrip.vehicleId}`}.
      </p>
      <label>
        Inspection notes
        <textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <label>
        Optional photo
        <input type="file" accept="image/*" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} />
      </label>
      <div className="button-strip">
        <button
          className="primary"
          onClick={() => {
            void onSubmitInspection(notes, photo).then(() => navigate(`/app/trips/end-review?reason=${encodeURIComponent(endReason)}`))
          }}
          type="button"
        >
          Submit inspection
        </button>
        <Link className="ghost-link" to="/app/trips">
          Cancel
        </Link>
      </div>
    </section>
  )
}

export function EndTripReviewPage({
  activeTrip,
  postTripInspectionResult,
  vehicles,
}: {
  activeTrip: Trip | null
  postTripInspectionResult: PostTripInspectionResult | null
  vehicles: Vehicle[]
}) {
  const [searchParams] = useSearchParams()
  const endReason = searchParams.get('reason') ?? 'USER_COMPLETED'
  const vehicle = vehicles.find((item) => item.id === activeTrip?.vehicleId) ?? null

  if (!postTripInspectionResult) {
    return (
      <section className="panel-card">
        <h2>No post-trip inspection found</h2>
        <p>Submit the mandatory inspection first.</p>
        <Link className="primary link-button" to={`/app/trips/end-inspection?reason=${encodeURIComponent(endReason)}`}>
          Go to inspection
        </Link>
      </section>
    )
  }

  return (
    <section className="panel-card">
      <p className="eyebrow">End trip step 2 of 3</p>
      <h1>Review the post-trip inspection result.</h1>
      <div className={`notice-card ${postTripInspectionResult.followUpRequired ? 'notice-card--error' : 'notice-card--success'}`}>
        <strong>{vehicle?.model ?? `Vehicle #${postTripInspectionResult.vehicleId}`}</strong>
        <p>Severity: {formatSeverityLabel(postTripInspectionResult.assessmentResult.severity)}</p>
        <p>{postTripInspectionResult.warningMessage}</p>
      </div>
      {endReason === 'SEVERE_INTERNAL_FAULT' ? (
        <div className="notice-card">
          <strong>Fault-driven end trip</strong>
          <p>You reported a severe in-trip issue. Once you confirm the lock command, FleetShare will finish the disrupted-trip flow and compute any compensation.</p>
        </div>
      ) : null}
      <div className="button-strip">
        <Link className="primary link-button" to={`/app/trips/end-confirm?reason=${encodeURIComponent(endReason)}`}>
          Continue to lock confirmation
        </Link>
      </div>
    </section>
  )
}

export function EndTripConfirmPage({
  activeTrip,
  onConfirmEndTrip,
  postTripInspectionResult,
  vehicles,
}: {
  activeTrip: Trip | null
  onConfirmEndTrip: (endReason: string) => Promise<EndTripResult>
  postTripInspectionResult: PostTripInspectionResult | null
  vehicles: Vehicle[]
}) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const endReason = searchParams.get('reason') ?? 'USER_COMPLETED'
  const vehicle = vehicles.find((item) => item.id === activeTrip?.vehicleId) ?? null

  if (!activeTrip || !postTripInspectionResult) {
    return (
      <section className="panel-card">
        <h2>End-trip wizard is incomplete</h2>
        <p>Complete the inspection step before confirming the lock action.</p>
        <Link className="primary link-button" to={`/app/trips/end-inspection?reason=${encodeURIComponent(endReason)}`}>
          Go to inspection
        </Link>
      </section>
    )
  }

  return (
    <section className="panel-card">
      <p className="eyebrow">End trip step 3 of 3</p>
      <h1>Confirm that the car is parked and ready to lock.</h1>
      <p className="hero-copy">
        When you confirm, FleetShare will send the final lock command for {vehicle?.model ?? `vehicle #${activeTrip.vehicleId}`} and complete the end-trip flow.
      </p>
      <div className="notice-card">
        <strong>Customer confirmation required</strong>
        <p>Only click this after the car is stopped safely, parked correctly, and you are ready for FleetShare to lock it.</p>
      </div>
      <div className="button-strip">
        <button
          className="primary"
          onClick={() => {
            void onConfirmEndTrip(endReason).then(() => navigate(`/app/trips/end-complete?reason=${encodeURIComponent(endReason)}`))
          }}
          type="button"
        >
          Lock car and end trip
        </button>
      </div>
    </section>
  )
}

export function EndTripCompletePage({
  endTripResult,
}: {
  endTripResult: EndTripResult | null
}) {
  if (!endTripResult) {
    return (
      <section className="panel-card">
        <h2>No completed end-trip result</h2>
        <p>Run the end-trip flow from the trip hub first.</p>
        <Link className="primary link-button" to="/app/trips">
          Back to trip hub
        </Link>
      </section>
    )
  }

  const settlementLabel = endTripResult.renewalReconciliationPending ? 'Renewal reconciliation' : 'Refund queued'
  const settlementValue = endTripResult.renewalReconciliationPending ? 'Pending' : endTripResult.refundPending ? 'Yes' : 'No'

  return (
    <div className="stack">
      <section className="booking-hero">
        <div>
          <p className="eyebrow">Trip completed</p>
          <h1>Your trip has been locked and closed.</h1>
          <p className="hero-copy">
            FleetShare has stored the post-trip inspection, sent the lock command, and finalized the fare adjustment outcome for this journey.
          </p>
        </div>
        <div className="summary-panel">
          <div>
            <span>Status</span>
            <strong>{endTripResult.tripStatus}</strong>
          </div>
          <div>
            <span>Vehicle locked</span>
            <strong>{endTripResult.vehicleLocked ? 'Yes' : 'No'}</strong>
          </div>
          <div>
            <span>Final fare</span>
            <strong>{formatMoney(endTripResult.adjustedFare)}</strong>
          </div>
        </div>
      </section>
      <section className="dashboard-grid">
        <article className="panel-card">
          <p className="mini-label">Fare outcome</p>
          <h2>Billing summary</h2>
          <div className="quote-grid">
            <div>
              <span>Final fare</span>
              <strong>{formatMoney(endTripResult.adjustedFare)}</strong>
            </div>
            <div>
              <span>Apology credit</span>
              <strong>{formatMoney(endTripResult.discountAmount)}</strong>
            </div>
            <div>
              <span>{(endTripResult.allowanceHoursRestored ?? 0) > 0 ? 'Allowance restored' : 'Allowance used'}</span>
              <strong>{formatHours((endTripResult.allowanceHoursRestored ?? 0) > 0 ? endTripResult.allowanceHoursRestored ?? 0 : endTripResult.allowanceHoursApplied)}</strong>
            </div>
            <div>
              <span>{settlementLabel}</span>
              <strong>{settlementValue}</strong>
            </div>
          </div>
        </article>
      </section>
      <div className="button-strip">
        <Link className="primary link-button" to="/app/trips">
          Return to trip hub
        </Link>
        <Link className="ghost-link" to="/app/account">
          View account summary
        </Link>
      </div>
    </div>
  )
}

export function AccountPage({
  customerSummary,
  notifications,
  payments,
}: {
  customerSummary: CustomerSummary | null
  notifications: Notification[]
  payments: { paymentId: number; amount: number; reason: string; status: string }[]
}) {
  return (
    <div className="stack">
      <section className="dashboard-grid">
        <article className="panel-card">
          <p className="mini-label">Plan status</p>
          <h2>{customerSummary?.planName.replaceAll('_', ' ') ?? 'Subscription'}</h2>
          <div className="quote-grid">
            <div>
              <span>Included per cycle</span>
              <strong>{formatHours(customerSummary?.monthlyIncludedHours ?? 0)}</strong>
            </div>
            <div>
              <span>Used this cycle</span>
              <strong>{formatHours(customerSummary?.hoursUsedThisCycle ?? 0)}</strong>
            </div>
            <div>
              <span>Remaining</span>
              <strong>{formatHours(customerSummary?.remainingHoursThisCycle ?? 0)}</strong>
            </div>
            <div>
              <span>Renews</span>
              <strong>{formatDateOnly(customerSummary?.subscriptionEndDate)}</strong>
            </div>
          </div>
        </article>

        <article className="panel-card">
          <p className="mini-label">Payments</p>
          <h2>Recent charges and adjustments</h2>
          <div className="history-list compact-list">
            {payments.map((payment) => (
              <article className="history-card" key={payment.paymentId}>
                <div>
                  <strong>{payment.reason.replaceAll('_', ' ')}</strong>
                  <p>{payment.status}</p>
                </div>
                <strong>{formatMoney(payment.amount)}</strong>
              </article>
            ))}
            {payments.length === 0 ? <div className="empty-card"><p>No payments yet.</p></div> : null}
          </div>
        </article>
      </section>

      <section className="panel-card">
        <p className="mini-label">Notifications</p>
        <h2>Customer inbox</h2>
        <div className="notification-stack">
          {notifications.map((notification) => (
            <article className="notification-card" key={notification.notificationId}>
              <strong>{notification.subject}</strong>
              <p>{notification.message}</p>
            </article>
          ))}
          {notifications.length === 0 ? <div className="empty-card"><p>No messages yet.</p></div> : null}
        </div>
      </section>
    </div>
  )
}
