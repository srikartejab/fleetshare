import { type Dispatch, type ReactNode, type SetStateAction, useState } from 'react'
import { Link, NavLink, useNavigate, useParams } from 'react-router-dom'

import {
  formatDate,
  formatDateTime,
  formatHours,
  formatMoney,
} from './appTypes'
import type { Booking, CustomerSummary, Notification, Trip, Vehicle, VehicleFilters } from './appTypes'

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
            <li>Overnight renewal with provisional charges</li>
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
                <strong>{formatDate(customer.renewalDate)}</strong>
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
            <span>Renewal date</span>
            <strong>{customerSummary ? formatDate(customerSummary.renewalDate) : '...'}</strong>
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
  onReserve: (vehicleId: number) => Promise<number>
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
                    {formatHours(vehicle.provisionalPostMidnightHours)} will be charged provisionally now and may be re-rated after renewal on {formatDate(vehicle.renewalDate)}.
                  </p>
                </div>
              ) : null}
              <div className="result-card__footer">
                <p>{vehicle.allowanceStatus}</p>
                <button
                  className="primary"
                  onClick={() => {
                    void onReserve(vehicle.vehicleId ?? vehicle.id).then((bookingId) => navigate(`/app/bookings/${bookingId}`))
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

export function BookingDetailsPage({
  bookings,
  customerSummary,
  vehicles,
}: {
  bookings: Booking[]
  customerSummary: CustomerSummary | null
  vehicles: Vehicle[]
}) {
  const { bookingId } = useParams()
  const booking = bookings.find((item) => String(item.bookingId) === bookingId) ?? null
  const vehicle = vehicles.find((item) => item.id === booking?.vehicleId) ?? null
  const pricing = booking?.pricingSnapshot

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
          <p className="eyebrow">Booking confirmed</p>
          <h1>Reservation #{booking.bookingId} is ready for the next step.</h1>
          <p className="hero-copy">
            Your booking is stored in the booking service while the pricing snapshot below shows exactly how allowance and provisional renewal charges were calculated at reservation time.
          </p>
        </div>
        <div className="summary-panel">
          <div>
            <span>Due now</span>
            <strong>{formatMoney(booking.displayedPrice)}</strong>
          </div>
          <div>
            <span>Status</span>
            <strong>{booking.status}</strong>
          </div>
          <div>
            <span>Renewal date</span>
            <strong>{customerSummary ? formatDate(customerSummary.renewalDate) : 'N/A'}</strong>
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

export function TripsPage({
  activeTrip,
  bookings,
  completedTrips,
  onEndTrip,
  onStartTrip,
  onSubmitInspection,
  upcomingBookings,
  vehicles,
}: {
  activeTrip: Trip | null
  bookings: Booking[]
  completedTrips: Trip[]
  onEndTrip: (bookingId: number, tripId: number, vehicleId: number, endReason: string) => Promise<void>
  onStartTrip: (bookingId: number, vehicleId: number, notes: string) => Promise<void>
  onSubmitInspection: (bookingId: number, vehicleId: number, notes: string, photo: File | null) => Promise<void>
  upcomingBookings: Booking[]
  vehicles: Vehicle[]
}) {
  const nextBooking = upcomingBookings[0] ?? null
  const nextVehicle = vehicles.find((vehicle) => vehicle.id === nextBooking?.vehicleId) ?? null
  const [inspectionNotes, setInspectionNotes] = useState('Vehicle exterior looks clean.')
  const [inspectionPhoto, setInspectionPhoto] = useState<File | null>(null)
  const [startNotes, setStartNotes] = useState('')
  const [endReason, setEndReason] = useState('USER_COMPLETED')

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
              <div className="button-strip">
                <button className="primary" onClick={() => void onSubmitInspection(nextBooking.bookingId, nextBooking.vehicleId, inspectionNotes, inspectionPhoto)} type="button">
                  Submit inspection
                </button>
                <button onClick={() => void onStartTrip(nextBooking.bookingId, nextBooking.vehicleId, startNotes)} type="button">
                  Start trip
                </button>
              </div>
              <label>
                Start notes
                <input value={startNotes} onChange={(event) => setStartNotes(event.target.value)} placeholder="Optional start notes" />
              </label>
            </>
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
              <p>Started {formatDateTime(activeTrip.startedAt)}</p>
              <label>
                End reason
                <select value={endReason} onChange={(event) => setEndReason(event.target.value)}>
                  <option value="USER_COMPLETED">Trip completed normally</option>
                  <option value="SEVERE_INTERNAL_FAULT">Vehicle issue during trip</option>
                </select>
              </label>
              <button className="primary" onClick={() => void onEndTrip(activeTrip.bookingId, activeTrip.tripId, activeTrip.vehicleId, endReason)} type="button">
                End trip
              </button>
            </>
          ) : (
            <div className="empty-card"><p>No active trip yet.</p></div>
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
              <strong>{formatDate(customerSummary?.renewalDate)}</strong>
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
