import { type ReactNode, useEffect, useState } from 'react'
import { Link, NavLink, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import {
  formatDate,
  formatDateTime,
  formatHours,
  formatMoney,
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
  WalletLedgerEntry,
} from './appTypes'
import './customerMobile.css'

function deviceTime() {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date())
}

function planLabel(planName?: string | null) {
  return planName?.replaceAll('_', ' ') ?? 'STANDARD MONTHLY'
}

function firstName(displayName?: string | null) {
  return displayName?.split(' ')[0] ?? 'User'
}

function pageTitle(pathname: string) {
  if (pathname.startsWith('/app/bookings/')) return 'Booking Details'
  if (pathname === '/app/bookings/processing') return 'Booking'
  if (pathname.startsWith('/app/trips/end-')) return 'End Trip'
  if (pathname === '/app/trips/report-problem') return 'Report Problem'
  if (pathname === '/app/trips/problem-advisory') return 'Problem Advisory'
  if (pathname === '/app/wallet') return 'Wallet'
  if (pathname === '/app/account') return 'Account'
  if (pathname === '/app/trips') return 'Bookings'
  return 'Home'
}

function vehicleDisplayName(vehicle?: Vehicle | null, fallbackId?: number | null) {
  if (vehicle?.model) return vehicle.model
  if (fallbackId) return `Vehicle #${fallbackId}`
  return 'Vehicle'
}

function vehicleTypeLabel(vehicle?: Vehicle | null) {
  switch (vehicle?.vehicleType) {
    case 'SUV':
      return 'Standard EV SUV'
    case 'COMPACT':
      return 'Compact EV'
    case 'LUXURY':
      return 'Premium EV'
    case 'MPV':
      return 'Family EV'
    case 'SEDAN':
    default:
      return 'Standard EV Sedan'
  }
}

function AccountIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="8" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M5.3 19.2a6.7 6.7 0 0 1 13.4 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function HomeIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4.5 9.8 12 4l7.5 5.8v8.8a1.5 1.5 0 0 1-1.5 1.5h-3.7v-6H9.7v6H6a1.5 1.5 0 0 1-1.5-1.5V9.8Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
    </svg>
  )
}

function TripsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="m8.6 12.2 2.2 2.2 4.5-4.7" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function WalletIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M5 8.2a2.2 2.2 0 0 1 2.2-2.2h10.1a1.7 1.7 0 0 1 1.7 1.7v1.1H7.2A2.2 2.2 0 0 0 5 11v5a2.2 2.2 0 0 0 2.2 2.2h10.6A1.2 1.2 0 0 0 19 17V8.2" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="M19 10.2h-5.7a1.8 1.8 0 0 0 0 3.6H19" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      <circle cx="13.5" cy="12" r="0.85" fill="currentColor" />
    </svg>
  )
}

function FinderIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M7 15.6h10l-1.4-4.6H8.4L7 15.6Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="m9 11 1.8-3.8h2.4L15 11" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" />
      <circle cx="8.8" cy="17.2" r="1.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="15.2" cy="17.2" r="1.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M12 4.5v2.2M9.8 5.6 8 4.2M14.2 5.6 16 4.2" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" />
    </svg>
  )
}

function ClockIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M12 7.4v5l3.4 2" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function PinIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 20.2s6-6 6-10.4A6 6 0 1 0 6 9.8c0 4.4 6 10.4 6 10.4Z" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="12" cy="9.5" r="2.4" fill="none" stroke="currentColor" strokeWidth="1.9" />
    </svg>
  )
}

function ArrowFlowIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 12h14M13 7l5 5-5 5" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" />
    </svg>
  )
}

function HeaderBackIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m14.5 5.5-6 6 6 6" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.3" />
    </svg>
  )
}

function ElectricIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M10.2 3.8 6.4 12h4.4l-1 8.2 7-10h-4.1l2.7-6.4Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
    </svg>
  )
}

function DriverIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="8" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M5.4 19.2a6.6 6.6 0 0 1 13.2 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m5.6 12.2 4 4 8.8-9" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m6.5 6.5 11 11M17.5 6.5l-11 11" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.1" />
    </svg>
  )
}

function CarArtwork() {
  return (
    <svg aria-hidden="true" className="customer-vehicle-art" viewBox="0 0 220 118">
      <defs>
        <linearGradient id="customer-car-body" x1="0%" x2="100%">
          <stop offset="0%" stopColor="#f9fbff" />
          <stop offset="100%" stopColor="#dbe6f5" />
        </linearGradient>
      </defs>
      <ellipse cx="106" cy="96" rx="78" ry="12" fill="rgba(17, 35, 61, 0.12)" />
      <path d="M36 73c6-23 19-35 38-38l40-7c16-3 31 1 45 11l17 13c6 4 10 11 10 19v10H28l8-8Z" fill="url(#customer-car-body)" />
      <path d="M80 34h45c10 0 20 3 28 9l13 9H65l15-18Z" fill="#eaf1fb" />
      <path d="M98 37h24l24 15H87l11-15Z" fill="#93a8c5" opacity="0.72" />
      <circle cx="66" cy="84" r="17" fill="#15243d" />
      <circle cx="66" cy="84" r="8" fill="#dfe6f1" />
      <circle cx="155" cy="84" r="17" fill="#15243d" />
      <circle cx="155" cy="84" r="8" fill="#dfe6f1" />
    </svg>
  )
}

function PageHeader({
  title,
  eyebrow,
  subtitle,
  backTo,
}: {
  title: string
  eyebrow?: string
  subtitle?: string
  backTo?: string
}) {
  return (
    <header className="customer-page-header">
      <div className="customer-page-header__row">
        {backTo ? (
          <Link className="customer-page-header__back" to={backTo}>
            <HeaderBackIcon />
          </Link>
        ) : null}
        <div className="customer-page-header__copy">
          {eyebrow ? <p className="customer-page-header__eyebrow">{eyebrow}</p> : null}
          <h1>{title}</h1>
        </div>
      </div>
      {subtitle ? <p className="customer-page-header__subtitle">{subtitle}</p> : null}
    </header>
  )
}

function EmptyState({
  title,
  body,
  actionLabel,
  actionTo,
}: {
  title: string
  body: string
  actionLabel?: string
  actionTo?: string
}) {
  return (
    <article className="customer-card customer-card--empty">
      <h2>{title}</h2>
      <p>{body}</p>
      {actionLabel && actionTo ? (
        <Link className="customer-button customer-button--primary link-button" to={actionTo}>
          {actionLabel}
        </Link>
      ) : null}
    </article>
  )
}

function BookingTimeline({
  startTime,
  endTime,
  location,
}: {
  startTime?: string | null
  endTime?: string | null
  location: string
}) {
  return (
    <div className="customer-timeline">
      <div className="customer-timeline__item">
        <ClockIcon />
        <div>
          <span>Pick Up</span>
          <strong>{formatDateTime(startTime)}</strong>
        </div>
      </div>
      <ArrowFlowIcon />
      <div className="customer-timeline__item">
        <ClockIcon />
        <div>
          <span>Drop Off</span>
          <strong>{formatDateTime(endTime)}</strong>
        </div>
      </div>
      <div className="customer-timeline__location">
        <PinIcon />
        <div>
          <span>Location</span>
          <strong>{location}</strong>
        </div>
      </div>
    </div>
  )
}

function BottomNav() {
  return (
    <nav className="customer-bottomnav">
      <NavLink className={({ isActive }) => `customer-bottomnav__item ${isActive ? 'customer-bottomnav__item--active' : ''}`} to="/app/account">
        <AccountIcon />
        <span>Account</span>
      </NavLink>
      <NavLink className={({ isActive }) => `customer-bottomnav__item ${isActive ? 'customer-bottomnav__item--active' : ''}`} to="/app/home">
        <HomeIcon />
        <span>Home</span>
      </NavLink>
      <NavLink className="customer-bottomnav__center" to="/app/discover">
        <FinderIcon />
      </NavLink>
      <NavLink className={({ isActive }) => `customer-bottomnav__item ${isActive ? 'customer-bottomnav__item--active' : ''}`} to="/app/trips">
        <TripsIcon />
        <span>Bookings</span>
      </NavLink>
      <NavLink className={({ isActive }) => `customer-bottomnav__item ${isActive ? 'customer-bottomnav__item--active' : ''}`} to="/app/wallet">
        <WalletIcon />
        <span>Wallet</span>
      </NavLink>
    </nav>
  )
}

function CustomerStatusPill({
  busy,
  status,
}: {
  busy: boolean
  status: string
}) {
  return <div className={`customer-status-pill ${busy ? 'customer-status-pill--busy' : ''}`}>{busy ? 'Updating...' : status}</div>
}

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
    <div className="customer-entry-shell">
      <div className="customer-entry-statusbar">
        <strong>{deviceTime()}</strong>
      </div>
      <section className="customer-entry-hero">
        <p className="customer-page-header__eyebrow">FleetShare Demo</p>
        <h1>Pick a driver and open the mobile customer experience.</h1>
        <p>The Discover map is already aligned to the reference style. The rest of the app now follows the same mobile-first language.</p>
        <CustomerStatusPill busy={busy} status={status} />
      </section>
      <section className="customer-entry-grid">
        {customers.map((customer) => (
          <article className="customer-entry-card" key={customer.userId}>
            <div>
              <p className="customer-page-header__eyebrow">{customer.demoBadge || 'Demo customer'}</p>
              <h2>{customer.displayName}</h2>
              <p>{planLabel(customer.planName)}</p>
            </div>
            <div className="customer-entry-stats">
              <div>
                <span>Remaining</span>
                <strong>{formatHours(customer.remainingHoursThisCycle)}</strong>
              </div>
              <div>
                <span>Renewal</span>
                <strong>{formatDate(customer.renewalDate)}</strong>
              </div>
            </div>
            <button
              className="customer-button customer-button--primary"
              onClick={() => {
                onSelectCustomer(customer.userId)
                navigate('/app/home')
              }}
              type="button"
            >
              Enter as {firstName(customer.displayName)}
            </button>
          </article>
        ))}
      </section>
      <footer className="customer-entry-footer">
        <Link to="/ops">Open ops console</Link>
      </footer>
    </div>
  )
}

export function CustomerShell({
  activeUser,
  busy: _busy,
  status: _status,
  onSwitchUser,
  children,
}: {
  activeUser: CustomerSummary | null
  busy: boolean
  status: string
  onSwitchUser: () => void
  children: ReactNode
}) {
  const location = useLocation()
  const [clock, setClock] = useState(() => deviceTime())

  useEffect(() => {
    const timer = window.setInterval(() => setClock(deviceTime()), 1_000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <div className="app-shell customer-mobile-shell">
      <div className="customer-mobile-shell__chrome">
        <div className="customer-mobile-statusbar">
          <strong>{clock}</strong>
          <button className="customer-mobile-userpill" onClick={onSwitchUser} type="button">
            {firstName(activeUser?.displayName)}
          </button>
        </div>
        <div className="customer-mobile-titlebar">
          <span>{pageTitle(location.pathname)}</span>
          <small>{planLabel(activeUser?.planName)}</small>
        </div>
      </div>
      <main className="customer-page customer-mobile-content">
        {children}
      </main>
      <BottomNav />
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
    <div className="customer-page-stack">
      <PageHeader
        eyebrow="Dashboard"
        subtitle="Subscription, next trip, and customer inbox in one mobile layout."
        title={customerSummary ? `${formatHours(customerSummary.remainingHoursThisCycle)} remaining this cycle` : 'Loading subscription'}
      />

      <section className="customer-hero-card customer-hero-card--blue">
        <div>
          <p className="customer-page-header__eyebrow">Plan overview</p>
          <h2>{planLabel(customerSummary?.planName)}</h2>
          <p>Your discover results and end-trip billing both feed from this allowance summary.</p>
        </div>
        <div className="customer-stat-grid">
          <div>
            <span>Used</span>
            <strong>{formatHours(customerSummary?.hoursUsedThisCycle ?? 0)}</strong>
          </div>
          <div>
            <span>Renews</span>
            <strong>{formatDate(customerSummary?.renewalDate)}</strong>
          </div>
          <div>
            <span>Hourly rate</span>
            <strong>{formatMoney(customerSummary?.hourlyRate ?? 0)}</strong>
          </div>
        </div>
      </section>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Next up</p>
            <h2>{activeTrip ? 'Active trip in progress' : 'Upcoming booking'}</h2>
          </div>
          <Link to="/app/trips">Open bookings</Link>
        </div>
        {activeTrip ? (
          <div className="customer-keyvalue-list">
            <div className="customer-keyvalue-row">
              <span>Trip</span>
              <strong>#{activeTrip.tripId}</strong>
            </div>
            <div className="customer-keyvalue-row">
              <span>Started</span>
              <strong>{formatDateTime(activeTrip.startedAt)}</strong>
            </div>
            <div className="customer-keyvalue-row">
              <span>Vehicle</span>
              <strong>#{activeTrip.vehicleId}</strong>
            </div>
          </div>
        ) : nextBooking ? (
          <>
            <div className="customer-pill-row">
              <span className="customer-status-tag customer-status-tag--info">{nextBooking.status}</span>
              <strong>Booking #{nextBooking.bookingId}</strong>
            </div>
            <BookingTimeline endTime={nextBooking.endTime} location={nextBooking.pickupLocation} startTime={nextBooking.startTime} />
          </>
        ) : (
          <EmptyState actionLabel="Find a vehicle" actionTo="/app/discover" body="No booking is queued yet for this customer profile." title="Nothing booked yet" />
        )}
      </article>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Inbox</p>
            <h2>Latest notifications</h2>
          </div>
          <Link to="/app/account">See all</Link>
        </div>
        <div className="customer-list-stack">
          {notifications.slice(0, 3).map((notification) => (
            <article className="customer-list-card" key={notification.notificationId}>
              <strong>{notification.subject}</strong>
              <p>{notification.message}</p>
            </article>
          ))}
          {notifications.length === 0 ? <p className="customer-empty-copy">No notifications yet.</p> : null}
        </div>
      </article>
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
    return <EmptyState actionLabel="Back to discover" actionTo="/app/discover" body="Start from the Discover map to reserve a vehicle." title="No booking in progress" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader
        backTo="/app/discover"
        eyebrow="Reservation"
        subtitle="The booking, payment, and confirmation flow stays the same. Only the UI treatment changed."
        title={
          pendingBooking.status === 'processing'
            ? 'Confirming your booking'
            : pendingBooking.status === 'success'
              ? `Booking #${pendingBooking.bookingId} confirmed`
              : 'Booking failed'
        }
      />
      <section className="customer-hero-card">
        <div>
          <p className="customer-page-header__eyebrow">Vehicle</p>
          <h2>{vehicleDisplayName(vehicle, pendingBooking.vehicleId)}</h2>
          <p>
            {pendingBooking.status === 'processing'
              ? 'We are reserving the slot, charging the booking, and saving the confirmation.'
              : pendingBooking.status === 'success'
                ? 'Your reservation is secured and the app will open the booking details screen next.'
                : pendingBooking.error ?? 'Please return to discover and try again.'}
          </p>
        </div>
        <CarArtwork />
      </section>
      <section className="customer-card">
        <div className="customer-step-list">
          <div className={`customer-step ${pendingBooking.status !== 'error' ? 'customer-step--done' : ''}`}>
            <strong>Reserve vehicle slot</strong>
            <span>{pendingBooking.status === 'error' ? 'Attempted' : 'Completed'}</span>
          </div>
          <div className={`customer-step ${pendingBooking.status === 'processing' ? 'customer-step--active' : pendingBooking.status === 'success' ? 'customer-step--done' : 'customer-step--error'}`}>
            <strong>Price and confirm booking</strong>
            <span>{pendingBooking.status === 'processing' ? 'In progress' : pendingBooking.status === 'success' ? 'Completed' : 'Failed'}</span>
          </div>
          <div className={`customer-step ${pendingBooking.status === 'success' ? 'customer-step--done' : ''}`}>
            <strong>Open booking details</strong>
            <span>{pendingBooking.status === 'success' ? 'Next' : 'Waiting'}</span>
          </div>
        </div>
        <div className="customer-action-row">
          {pendingBooking.status === 'success' && pendingBooking.bookingId ? (
            <Link className="customer-button customer-button--primary link-button" to={`/app/bookings/${pendingBooking.bookingId}`}>
              Open booking details
            </Link>
          ) : null}
          {pendingBooking.status === 'error' ? (
            <Link className="customer-button customer-button--secondary link-button" to="/app/discover">
              Back to discover
            </Link>
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
    return <EmptyState actionLabel="Back to bookings" actionTo="/app/trips" body="This booking is not loaded in the current session yet." title="Booking not found" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader backTo="/app/trips" eyebrow="Reservation" title="Booking Details" />

      <section className="customer-hero-card customer-hero-card--angled">
        <div>
          <p className="customer-page-header__eyebrow">Vehicle</p>
          <h2>{vehicleDisplayName(vehicle, booking.vehicleId)} <em>or similar</em></h2>
          <div className="customer-meta-row">
            <span><PinIcon /> 0.16 km</span>
            <span><DriverIcon /> New Driver</span>
            <span><ElectricIcon /> Electric</span>
          </div>
          <p>{vehicleTypeLabel(vehicle)}</p>
        </div>
        <CarArtwork />
      </section>

      <article className="customer-card customer-card--info">
        <h2>Why is there no mileage fee?</h2>
        <p>Pricing in this demo is driven by included subscription hours, extra billable hours, and any overnight provisional charge that may be reconciled after renewal.</p>
      </article>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Trip status</p>
            <h2>Pick up and return</h2>
          </div>
          <Link to="/app/discover">View map</Link>
        </div>
        <BookingTimeline endTime={booking.endTime} location={booking.pickupLocation} startTime={booking.startTime} />
      </article>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Included</p>
            <h2>Reservation coverage</h2>
          </div>
        </div>
        <div className="customer-checklist">
          <div className="customer-checklist__block">
            <span>Included</span>
            <ul>
              <li><CheckIcon /> Basic Vehicle Insurance</li>
              <li><CheckIcon /> Physical Vehicle Key/Remote</li>
              <li><CheckIcon /> 24/7 Emergency Hotline</li>
            </ul>
          </div>
          <div className="customer-checklist__block">
            <span>Excluded</span>
            <ul className="customer-checklist__block--muted">
              <li><CloseIcon /> Additional Insurance Coverage</li>
            </ul>
          </div>
        </div>
      </article>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Rental fees</p>
            <h2>{formatMoney(booking.displayedPrice)}</h2>
          </div>
          <span className="customer-status-tag customer-status-tag--info">{booking.status}</span>
        </div>
        <div className="customer-keyvalue-list">
          <div className="customer-keyvalue-row">
            <span>Trip duration</span>
            <strong>{formatHours(pricing?.totalHours ?? 0)}</strong>
          </div>
          <div className="customer-keyvalue-row">
            <span>Included now</span>
            <strong>{formatHours(pricing?.includedHoursApplied ?? 0)}</strong>
          </div>
          <div className="customer-keyvalue-row">
            <span>Remaining after booking</span>
            <strong>{formatHours(pricing?.includedHoursRemainingAfter ?? 0)}</strong>
          </div>
          <div className="customer-keyvalue-row">
            <span>Extra billed hours</span>
            <strong>{formatHours(pricing?.billableHours ?? 0)}</strong>
          </div>
          {pricing?.provisionalPostMidnightHours ? (
            <div className="customer-keyvalue-row">
              <span>Overnight provisional charge</span>
              <strong>{formatMoney(pricing.provisionalCharge)}</strong>
            </div>
          ) : null}
          <div className="customer-keyvalue-row">
            <span>Renewal date</span>
            <strong>{customerSummary ? formatDate(customerSummary.renewalDate) : 'N/A'}</strong>
          </div>
        </div>
        <div className="customer-action-row">
          <Link className="customer-button customer-button--primary link-button" to="/app/trips">
            Continue to bookings
          </Link>
        </div>
      </article>
    </div>
  )
}

export function TripsPage({
  activeTrip,
  completedTrips,
  historicalBookings,
  latestInspectionResult,
  onCancelModerateDamage,
  onStartTrip,
  onSubmitInspection,
  upcomingBookings,
  vehicles,
  records,
}: {
  activeTrip: Trip | null
  completedTrips: Trip[]
  historicalBookings: Booking[]
  latestInspectionResult: InspectionSubmissionResult | null
  onCancelModerateDamage: (bookingId: number, vehicleId: number) => Promise<void>
  onStartTrip: (bookingId: number, vehicleId: number, notes: string) => Promise<void>
  onSubmitInspection: (bookingId: number, vehicleId: number, notes: string, photo: File | null) => Promise<void>
  upcomingBookings: Booking[]
  vehicles: Vehicle[]
  records: RecordItem[]
}) {
  const [tab, setTab] = useState<'active' | 'past'>('active')
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
    <div className="customer-page-stack">
      <PageHeader eyebrow="Trips" title="Bookings" />

      <div className="customer-tabs">
        <button className={`customer-tab ${tab === 'active' ? 'customer-tab--active' : ''}`} onClick={() => setTab('active')} type="button">
          Active
        </button>
        <button className={`customer-tab ${tab === 'past' ? 'customer-tab--active' : ''}`} onClick={() => setTab('past')} type="button">
          Past
        </button>
      </div>

      {tab === 'active' ? (
        <>
          {nextBooking ? (
            <article className="customer-booking-card">
              <div className="customer-booking-card__top">
                <div>
                  <p className="customer-booking-card__code">B-{String(nextBooking.bookingId).padStart(6, '0')}</p>
                  <h2>{vehicleDisplayName(nextVehicle, nextBooking.vehicleId)}</h2>
                  <span className="customer-status-tag customer-status-tag--info">{nextBooking.status}</span>
                </div>
                <CarArtwork />
              </div>
              <BookingTimeline endTime={nextBooking.endTime} location={nextBooking.pickupLocation} startTime={nextBooking.startTime} />
              <div className="customer-card__divider" />
              <div className="customer-form-stack">
                <label>
                  Inspection notes
                  <textarea rows={3} value={inspectionNotes} onChange={(event) => setInspectionNotes(event.target.value)} />
                </label>
                <label>
                  Optional photo
                  <input accept="image/*" onChange={(event) => setInspectionPhoto(event.target.files?.[0] ?? null)} type="file" />
                </label>
                <div className={`customer-inline-notice ${inspectionCleared ? 'customer-inline-notice--success' : inspectionRecord ? 'customer-inline-notice--warning' : ''}`}>
                  <strong>Inspection gate</strong>
                  <p>
                    {inspectionCleared
                      ? moderateInspection
                        ? 'Moderate damage was logged. You can still unlock the vehicle or cancel the booking to escalate the incident.'
                        : 'Inspection cleared. You can unlock the vehicle and start the trip.'
                      : inspectionRecord
                        ? `Inspection status: ${inspectionRecord.reviewState}. Unlock stays disabled until the review clears.`
                        : 'Submit the external inspection first. Unlock remains disabled until a cleared result exists.'}
                  </p>
                </div>
                <label>
                  Start notes
                  <input onChange={(event) => setStartNotes(event.target.value)} placeholder="Optional notes sent with the unlock command" value={startNotes} />
                </label>
                <div className="customer-action-row">
                  <button className="customer-button customer-button--primary" onClick={() => void onSubmitInspection(nextBooking.bookingId, nextBooking.vehicleId, inspectionNotes, inspectionPhoto)} type="button">
                    Submit inspection
                  </button>
                  <button className="customer-button customer-button--secondary" disabled={!inspectionCleared} onClick={() => void onStartTrip(nextBooking.bookingId, nextBooking.vehicleId, startNotes)} type="button">
                    Unlock vehicle
                  </button>
                  {moderateInspection ? (
                    <button className="customer-button customer-button--ghost" onClick={() => void onCancelModerateDamage(nextBooking.bookingId, nextBooking.vehicleId)} type="button">
                      Cancel due to damage
                    </button>
                  ) : null}
                </div>
              </div>
            </article>
          ) : (
            <EmptyState actionLabel="Find a vehicle" actionTo="/app/discover" body="You do not have any upcoming bookings. Reserve a vehicle to start the trip flow." title="No upcoming bookings" />
          )}

          <article className="customer-card">
            <div className="customer-card__header">
              <div>
                <p className="customer-page-header__eyebrow">Live trip</p>
                <h2>Active trip control</h2>
              </div>
            </div>
            {activeTrip ? (
              <>
                <div className="customer-pill-row">
                  <span className="customer-status-tag customer-status-tag--success">{activeTrip.status}</span>
                  <strong>Trip #{activeTrip.tripId}</strong>
                </div>
                <div className="customer-keyvalue-list">
                  <div className="customer-keyvalue-row">
                    <span>Started</span>
                    <strong>{formatDateTime(activeTrip.startedAt)}</strong>
                  </div>
                  <div className="customer-keyvalue-row">
                    <span>Duration</span>
                    <strong>{formatHours(activeTrip.durationHours)}</strong>
                  </div>
                </div>
                <div className="customer-action-row">
                  <Link className="customer-button customer-button--primary link-button" to="/app/trips/end-inspection?reason=USER_COMPLETED">
                    End trip
                  </Link>
                  <Link className="customer-button customer-button--secondary link-button" to="/app/trips/report-problem">
                    Report problem
                  </Link>
                </div>
              </>
            ) : (
              <p className="customer-empty-copy">No active trip yet. A cleared inspection alone does not start the trip; the customer must still unlock the vehicle.</p>
            )}
          </article>
        </>
      ) : (
        <section className="customer-list-stack">
          {historicalBookings.map((booking) => {
            const trip = completedTrips.find((item) => item.bookingId === booking.bookingId) ?? null
            const vehicle = vehicles.find((item) => item.id === booking.vehicleId)
            return (
              <article className="customer-booking-card customer-booking-card--compact" key={booking.bookingId}>
                <div className="customer-booking-card__top">
                  <div>
                    <p className="customer-booking-card__code">B-{String(booking.bookingId).padStart(6, '0')}</p>
                    <h2>{vehicleDisplayName(vehicle, booking.vehicleId)}</h2>
                    <span className="customer-status-tag">{booking.status}</span>
                  </div>
                  <CarArtwork />
                </div>
                <BookingTimeline
                  endTime={trip?.endedAt ?? booking.endTime}
                  location={booking.pickupLocation ?? 'Return station unavailable'}
                  startTime={trip?.startedAt ?? booking.startTime}
                />
                <div className="customer-link-row">
                  <strong>{formatMoney(booking.finalPrice ?? booking.displayedPrice ?? 0)}</strong>
                  <Link to={`/app/bookings/${booking.bookingId}`}>View Details</Link>
                </div>
              </article>
            )
          })}
          {historicalBookings.length === 0 ? <EmptyState body="Once this customer has a completed or cancelled booking, it will appear here." title="No past bookings" /> : null}
        </section>
      )}
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
    return <EmptyState actionLabel="Back to bookings" actionTo="/app/trips" body="You can only report an in-trip problem while a trip is active." title="No active trip" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader backTo="/app/trips" eyebrow="Trip problem" title="Report a vehicle issue" />
      <article className="customer-card">
        <p>Submit a short description of the fault. FleetShare will assess the issue and decide whether the trip should continue or end early.</p>
        <label>
          Problem description
          <textarea rows={5} value={notes} onChange={(event) => setNotes(event.target.value)} />
        </label>
        <div className="customer-action-row">
          <button
            className="customer-button customer-button--primary"
            disabled={!notes.trim()}
            onClick={() => {
              void onSubmitProblem(notes).then(() => navigate('/app/trips/problem-advisory'))
            }}
            type="button"
          >
            Submit problem
          </button>
        </div>
      </article>
    </div>
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
    return <EmptyState actionLabel="Back to bookings" actionTo="/app/trips" body="Start from the active trip page to submit a vehicle problem." title="No problem report found" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader backTo="/app/trips" eyebrow="Problem assessment" title={reportedProblem.blocked ? 'Stop safely and end the trip' : 'The report has been recorded'} />
      <article className={`customer-card customer-card--${reportedProblem.blocked ? 'danger' : 'success'}`}>
        <h2>Severity: {reportedProblem.severity}</h2>
        <p>{reportedProblem.recommendedAction}</p>
        {reportedProblem.duplicateSuppressed ? <p>FleetShare detected a matching incident and suppressed a duplicate recovery run.</p> : null}
      </article>
      <div className="customer-action-row">
        {reportedProblem.blocked && activeTrip ? (
          <Link className="customer-button customer-button--primary link-button" to="/app/trips/end-inspection?reason=SEVERE_INTERNAL_FAULT">
            Continue to end trip
          </Link>
        ) : (
          <Link className="customer-button customer-button--primary link-button" to="/app/trips">
            Return to bookings
          </Link>
        )}
      </div>
    </div>
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
    return <EmptyState actionLabel="Back to bookings" actionTo="/app/trips" body="The end-trip flow starts from an active trip." title="No active trip" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader backTo="/app/trips" eyebrow="End trip step 1 of 3" title="Complete the post-trip inspection" />
      <section className="customer-hero-card">
        <div>
          <h2>{vehicleDisplayName(vehicle, activeTrip.vehicleId)}</h2>
          <p>Record the exterior condition before you confirm the final lock command.</p>
        </div>
        <CarArtwork />
      </section>
      <article className="customer-card">
        <label>
          Inspection notes
          <textarea rows={4} value={notes} onChange={(event) => setNotes(event.target.value)} />
        </label>
        <label>
          Optional photo
          <input accept="image/*" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} type="file" />
        </label>
        <div className="customer-action-row">
          <button
            className="customer-button customer-button--primary"
            onClick={() => {
              void onSubmitInspection(notes, photo).then(() => navigate(`/app/trips/end-review?reason=${encodeURIComponent(endReason)}`))
            }}
            type="button"
          >
            Submit inspection
          </button>
        </div>
      </article>
    </div>
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
    return <EmptyState actionLabel="Go to inspection" actionTo={`/app/trips/end-inspection?reason=${encodeURIComponent(endReason)}`} body="Submit the mandatory inspection first." title="No post-trip inspection found" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader backTo={`/app/trips/end-inspection?reason=${encodeURIComponent(endReason)}`} eyebrow="End trip step 2 of 3" title="Review the inspection result" />
      <article className={`customer-card customer-card--${postTripInspectionResult.followUpRequired ? 'warning' : 'success'}`}>
        <h2>{vehicleDisplayName(vehicle, postTripInspectionResult.vehicleId)}</h2>
        <p>Severity: {postTripInspectionResult.assessmentResult.severity}</p>
        <p>{postTripInspectionResult.warningMessage}</p>
      </article>
      {endReason === 'SEVERE_INTERNAL_FAULT' ? (
        <article className="customer-card customer-card--info">
          <h2>Fault-driven end trip</h2>
          <p>Because the trip is ending due to an internal fault, FleetShare will also run the disruption compensation path after the lock command succeeds.</p>
        </article>
      ) : null}
      <div className="customer-action-row">
        <Link className="customer-button customer-button--primary link-button" to={`/app/trips/end-confirm?reason=${encodeURIComponent(endReason)}`}>
          Continue to lock confirmation
        </Link>
      </div>
    </div>
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
    return <EmptyState actionLabel="Go to inspection" actionTo={`/app/trips/end-inspection?reason=${encodeURIComponent(endReason)}`} body="Complete the inspection step before confirming the lock action." title="End-trip flow is incomplete" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader backTo={`/app/trips/end-review?reason=${encodeURIComponent(endReason)}`} eyebrow="End trip step 3 of 3" title="Confirm the final lock" />
      <section className="customer-hero-card">
        <div>
          <h2>{vehicleDisplayName(vehicle, activeTrip.vehicleId)}</h2>
          <p>Only continue after the car is parked safely and ready for FleetShare to lock.</p>
        </div>
        <CarArtwork />
      </section>
      <article className="customer-card customer-card--info">
        <h2>Customer confirmation required</h2>
        <p>When you confirm, FleetShare sends the final lock command and closes the trip with the correct fare adjustment.</p>
      </article>
      <div className="customer-action-row">
        <button
          className="customer-button customer-button--primary"
          onClick={() => {
            void onConfirmEndTrip(endReason).then(() => navigate(`/app/trips/end-complete?reason=${encodeURIComponent(endReason)}`))
          }}
          type="button"
        >
          Lock car and end trip
        </button>
      </div>
    </div>
  )
}

export function EndTripCompletePage({
  endTripResult,
  postTripInspectionResult,
}: {
  endTripResult: EndTripResult | null
  postTripInspectionResult: PostTripInspectionResult | null
}) {
  if (!endTripResult) {
    return <EmptyState actionLabel="Back to bookings" actionTo="/app/trips" body="Run the end-trip flow from the bookings page first." title="No completed end-trip result" />
  }

  return (
    <div className="customer-page-stack">
      <PageHeader eyebrow="Trip completed" title="Your trip has been closed" />
      <section className="customer-hero-card customer-hero-card--blue">
        <div>
          <h2>{formatMoney(endTripResult.adjustedFare)}</h2>
          <p>FleetShare stored the post-trip inspection, sent the lock command, and finalized the billing outcome.</p>
        </div>
        <div className="customer-stat-grid">
          <div>
            <span>Status</span>
            <strong>{endTripResult.tripStatus}</strong>
          </div>
          <div>
            <span>Vehicle locked</span>
            <strong>{endTripResult.vehicleLocked ? 'Yes' : 'No'}</strong>
          </div>
          <div>
            <span>Refund pending</span>
            <strong>{endTripResult.refundPending ? 'Yes' : 'No'}</strong>
          </div>
        </div>
      </section>
      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Fare outcome</p>
            <h2>Billing summary</h2>
          </div>
        </div>
        <div className="customer-keyvalue-list">
          <div className="customer-keyvalue-row">
            <span>Final fare</span>
            <strong>{formatMoney(endTripResult.adjustedFare)}</strong>
          </div>
          <div className="customer-keyvalue-row">
            <span>Discount applied</span>
            <strong>{formatMoney(endTripResult.discountAmount)}</strong>
          </div>
          <div className="customer-keyvalue-row">
            <span>Allowance used</span>
            <strong>{formatHours(endTripResult.allowanceHoursApplied)}</strong>
          </div>
        </div>
      </article>
      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Inspection outcome</p>
            <h2>Post-trip evidence</h2>
          </div>
        </div>
        {postTripInspectionResult ? (
          <>
            <p>Severity: {postTripInspectionResult.assessmentResult.severity}</p>
            <p>{postTripInspectionResult.warningMessage}</p>
          </>
        ) : (
          <p>No post-trip inspection record was stored in this session.</p>
        )}
      </article>
      <div className="customer-action-row">
        <Link className="customer-button customer-button--primary link-button" to="/app/trips">
          Return to bookings
        </Link>
        <Link className="customer-button customer-button--secondary link-button" to="/app/account">
          View account summary
        </Link>
      </div>
    </div>
  )
}

function titleCaseWords(value: string) {
  return value
    .replaceAll(/[_\.]+/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (character) => character.toUpperCase())
}

export function WalletPage({
  customerSummary,
  bookings,
  payments,
  ledgerEntries,
}: {
  customerSummary: CustomerSummary | null
  bookings: Booking[]
  payments: Payment[]
  ledgerEntries: WalletLedgerEntry[]
}) {
  const bookingsById = new Map(bookings.map((booking) => [booking.bookingId, booking]))
  const paymentsByBookingId = new Map<number, Payment[]>()
  const ledgerBookingIds = new Set(ledgerEntries.map((entry) => entry.bookingId))

  for (const payment of payments) {
    if (!payment.bookingId) continue
    const existing = paymentsByBookingId.get(payment.bookingId) ?? []
    existing.push(payment)
    paymentsByBookingId.set(payment.bookingId, existing)
  }

  const bookingHourTransactions = bookings.flatMap((booking) => {
    const includedHoursApplied = booking.pricingSnapshot?.includedHoursApplied ?? 0
    if (includedHoursApplied <= 0 || ledgerBookingIds.has(booking.bookingId)) {
      return []
    }

    const bookingPayments = paymentsByBookingId.get(booking.bookingId) ?? []
    const provisionalCharge = bookingPayments.find((payment) => payment.reason === 'BOOKING_PROVISIONAL_CHARGE') ?? null
    const refundOrAdjustment = bookingPayments.find((payment) => payment.status === 'REFUNDED' || payment.status === 'ADJUSTED') ?? null
    const reservedHours = {
      id: `booking-hours-held-${booking.bookingId}`,
      postedAt: provisionalCharge?.createdAt ?? booking.startTime,
      category: 'HOURS',
      title: 'Included hours reserved',
      tone: 'hours',
      amountLabel: `-${formatHours(includedHoursApplied)}`,
      subtitle: `Booking #${booking.bookingId} - ${booking.pickupLocation}`,
      detail: `Reserved during booking confirmation for ${formatDateTime(booking.startTime)} to ${formatDateTime(booking.endTime)}`,
      chips: [booking.status, 'Allowance hold'],
    }

    if (booking.status !== 'CANCELLED' && booking.status !== 'RECONCILED') {
      return [reservedHours]
    }

    return [
      reservedHours,
      {
        id: `booking-hours-restored-${booking.bookingId}`,
        postedAt: refundOrAdjustment?.createdAt ?? booking.endTime ?? booking.startTime,
        category: 'HOURS',
        title: 'Included hours restored',
        tone: 'credit',
        amountLabel: `+${formatHours(includedHoursApplied)}`,
        subtitle: `Booking #${booking.bookingId} - ${booking.pickupLocation}`,
        detail: booking.cancellationReason
          ? `Returned after ${titleCaseWords(booking.cancellationReason)}`
          : 'Returned after booking cancellation',
        chips: [booking.status, 'Allowance refund'],
      },
    ]
  })

  const transactions = [
    ...bookingHourTransactions,
    ...payments.map((payment) => {
      const booking = payment.bookingId ? bookingsById.get(payment.bookingId) ?? null : null
      const isCredit = payment.status === 'REFUNDED' || payment.status === 'ADJUSTED'
      const title =
        payment.reason === 'BOOKING_PROVISIONAL_CHARGE'
          ? 'Booking charge captured'
          : payment.status === 'REFUNDED'
            ? 'Refund processed'
            : payment.status === 'ADJUSTED'
              ? 'Adjustment applied'
              : titleCaseWords(payment.reason)

      return {
        id: `payment-${payment.paymentId}`,
        postedAt: payment.createdAt ?? null,
        category: 'PAYMENT',
        title,
        tone: isCredit ? 'credit' : 'debit',
        amountLabel: `${isCredit ? '+' : '-'}${formatMoney(payment.amount)}`,
        subtitle: booking
          ? `Booking #${booking.bookingId} - ${booking.pickupLocation}`
          : `Payment #${payment.paymentId}`,
        detail: booking
          ? `${formatDateTime(booking.startTime)} to ${formatDateTime(booking.endTime)}`
          : payment.status,
        chips: [payment.status, payment.reason === 'BOOKING_PROVISIONAL_CHARGE' ? 'Invoice' : titleCaseWords(payment.reason)],
      }
    }),
    ...ledgerEntries.map((entry) => {
      const booking = bookingsById.get(entry.bookingId) ?? null
      const positiveHours = entry.includedHoursAfterRenewal > 0
      const hoursValue = positiveHours ? entry.includedHoursAfterRenewal : entry.includedHoursApplied
      const amountLabel = `${positiveHours ? '+' : '-'}${formatHours(hoursValue)}`
      const chips = []

      if (entry.billableHours > 0) chips.push(`Billable ${formatHours(entry.billableHours)}`)
      if (entry.refundAmount > 0) chips.push(`Refund ${formatMoney(entry.refundAmount)}`)
      if (entry.provisionalPostMidnightHours > 0) chips.push(`Overnight ${formatHours(entry.provisionalPostMidnightHours)}`)
      if (entry.reconciliationStatus !== 'NONE') chips.push(titleCaseWords(entry.reconciliationStatus))

      return {
        id: `ledger-${entry.ledgerId}`,
        postedAt: entry.updatedAt ?? entry.endTime ?? entry.createdAt ?? null,
        category: entry.entryType,
        title: entry.entryType === 'RENEWAL' ? 'Renewal reconciliation' : 'Included hours settled',
        tone: positiveHours ? 'credit' : 'hours',
        amountLabel,
        subtitle: booking
          ? `Booking #${booking.bookingId} - ${booking.pickupLocation}`
          : `Trip settlement #${entry.tripId ?? entry.bookingId}`,
        detail:
          entry.entryType === 'RENEWAL'
            ? `Final fare ${formatMoney(entry.finalPrice)} after renewal recalculation`
            : `Final fare ${formatMoney(entry.finalPrice)} for ${formatHours(entry.totalHours)} reserved`,
        chips,
      }
    }),
  ].sort((left, right) => new Date(right.postedAt ?? 0).getTime() - new Date(left.postedAt ?? 0).getTime())

  return (
    <div className="customer-page-stack">
      <PageHeader
        eyebrow="E-Wallet"
        subtitle="All money movement, hour usage, refunds, and renewal reconciliations for this customer profile."
        title="Transaction history"
      />

      <section className="customer-hero-card customer-hero-card--blue">
        <div>
          <p className="customer-page-header__eyebrow">Wallet summary</p>
          <h2>{planLabel(customerSummary?.planName)}</h2>
          <p>Booking deductions, refunds, included-hour usage, and any post-renewal reconciliation are consolidated here.</p>
        </div>
        <div className="customer-stat-grid">
          <div>
            <span>Remaining</span>
            <strong>{formatHours(customerSummary?.remainingHoursThisCycle ?? 0)}</strong>
          </div>
          <div>
            <span>Renews</span>
            <strong>{formatDate(customerSummary?.renewalDate)}</strong>
          </div>
          <div>
            <span>Hourly rate</span>
            <strong>{formatMoney(customerSummary?.hourlyRate ?? 0)}</strong>
          </div>
          <div>
            <span>Entries</span>
            <strong>{transactions.length}</strong>
          </div>
        </div>
      </section>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">History</p>
            <h2>All transactions</h2>
          </div>
        </div>
        <div className="customer-list-stack">
          {transactions.map((transaction) => (
            <article className="customer-transaction-card" key={transaction.id}>
              <div className="customer-transaction-card__top">
                <div>
                  <p className="customer-transaction-card__eyebrow">{transaction.category}</p>
                  <strong>{transaction.title}</strong>
                </div>
                <strong className={`customer-transaction-amount customer-transaction-amount--${transaction.tone}`}>{transaction.amountLabel}</strong>
              </div>
              <p className="customer-transaction-card__subtitle">{transaction.subtitle}</p>
              <p className="customer-transaction-card__detail">{transaction.detail}</p>
              <div className="customer-transaction-card__meta">
                <span>{formatDateTime(transaction.postedAt)}</span>
                <div className="customer-pill-row">
                  {transaction.chips.map((chip) => (
                    <span className="customer-status-tag" key={`${transaction.id}-${chip}`}>{chip}</span>
                  ))}
                </div>
              </div>
            </article>
          ))}
          {transactions.length === 0 ? (
            <p className="customer-empty-copy">No wallet transactions have been recorded for this user yet.</p>
          ) : null}
        </div>
      </article>
    </div>
  )
}

export function AccountPage({
  customerSummary,
  notifications,
}: {
  customerSummary: CustomerSummary | null
  notifications: Notification[]
}) {
  return (
    <div className="customer-page-stack">
      <PageHeader eyebrow="Profile" title="Account" />
      <section className="customer-hero-card customer-hero-card--blue">
        <div>
          <p className="customer-page-header__eyebrow">Plan status</p>
          <h2>{planLabel(customerSummary?.planName)}</h2>
          <p>Your current included-hour balance and billing adjustments are summarized here.</p>
        </div>
        <div className="customer-stat-grid">
          <div>
            <span>Included</span>
            <strong>{formatHours(customerSummary?.monthlyIncludedHours ?? 0)}</strong>
          </div>
          <div>
            <span>Used</span>
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
      </section>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Wallet</p>
            <h2>Open transaction history</h2>
          </div>
        </div>
        <p className="customer-inline-notice">Open the Wallet tab to review booking deductions, refunds, included-hour settlements, and renewal reconciliation history.</p>
        <div className="customer-action-row">
          <Link className="customer-button customer-button--secondary link-button" to="/app/wallet">
            Open wallet
          </Link>
        </div>
      </article>

      <article className="customer-card">
        <div className="customer-card__header">
          <div>
            <p className="customer-page-header__eyebrow">Notifications</p>
            <h2>Customer inbox</h2>
          </div>
        </div>
        <div className="customer-list-stack">
          {notifications.map((notification) => (
            <article className="customer-list-card" key={notification.notificationId}>
              <strong>{notification.subject}</strong>
              <p>{notification.message}</p>
            </article>
          ))}
          {notifications.length === 0 ? <p className="customer-empty-copy">No messages yet.</p> : null}
        </div>
      </article>
    </div>
  )
}
