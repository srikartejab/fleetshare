import { startTransition, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import {
  opsFetchJson,
  formatDateTime,
  formatHours,
  formatMoney,
  formatSeverityLabel,
} from './appTypes'
import type { Booking, CustomerSummary, Notification, OpsDashboardResponse, OpsTicketDetailResponse, Payment, RecordItem, Ticket, Trip, Vehicle } from './appTypes'
import './customerMobile.css'

type OpsSection = 'fleet' | 'tickets' | 'inbox' | 'actions' | 'billing'

function deviceTime() {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date())
}

function FleetIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M7 15.6h10l-1.4-4.6H8.4L7 15.6Z" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="m9 11 1.8-3.8h2.4L15 11" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.9" />
      <circle cx="8.8" cy="17.2" r="1.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <circle cx="15.2" cy="17.2" r="1.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
    </svg>
  )
}

function TicketsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M6 6.2h12a1.2 1.2 0 0 1 1.2 1.2v3.1a1.8 1.8 0 0 0 0 3.6v3.1a1.2 1.2 0 0 1-1.2 1.2H6a1.2 1.2 0 0 1-1.2-1.2v-3.1a1.8 1.8 0 0 0 0-3.6V7.4A1.2 1.2 0 0 1 6 6.2Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="M9.2 9.4h5.6M9.2 12h5.6M9.2 14.6h3.2" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function InboxIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4.8 8.2A2.2 2.2 0 0 1 7 6h10a2.2 2.2 0 0 1 2.2 2.2v7.6A2.2 2.2 0 0 1 17 18H7a2.2 2.2 0 0 1-2.2-2.2V8.2Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="m5.5 8.3 6.5 5 6.5-5" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
    </svg>
  )
}

function ActionsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M13.8 4.5a4.1 4.1 0 0 1 5.7 5.7l-8.1 8.1a2.4 2.4 0 0 1-1 .6l-3 .8.8-3a2.4 2.4 0 0 1 .6-1l8.1-8.1Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="m12.5 5.8 5.7 5.7" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function BillingIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M6.2 5h11.6a1.2 1.2 0 0 1 1.2 1.2v11.6a1.2 1.2 0 0 1-1.2 1.2H6.2A1.2 1.2 0 0 1 5 17.8V6.2A1.2 1.2 0 0 1 6.2 5Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      <path d="M8.5 9h7M8.5 12h7M8.5 15h4" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function OpsSectionHeader({
  eyebrow,
  title,
  subtitle,
}: {
  eyebrow: string
  title: string
  subtitle: string
}) {
  return (
    <header className="customer-page-header">
      <div className="customer-page-header__row">
        <div className="customer-page-header__copy">
          <p className="customer-page-header__eyebrow">{eyebrow}</p>
          <h1>{title}</h1>
        </div>
      </div>
      <p className="customer-page-header__subtitle">{subtitle}</p>
    </header>
  )
}

function OpsMetricCard({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function OpsNavButton({
  active,
  count,
  icon,
  label,
  onClick,
}: {
  active: boolean
  count?: number
  icon: ReactNode
  label: string
  onClick: () => void
}) {
  return (
    <button className={`ops-mobile-bottomnav__item ${active ? 'ops-mobile-bottomnav__item--active' : ''}`} onClick={onClick} type="button">
      <span className="ops-mobile-bottomnav__iconwrap">
        {icon}
        {count && count > 0 ? <small className="ops-mobile-bottomnav__count">{count}</small> : null}
      </span>
      <span>{label}</span>
    </button>
  )
}

function OpsStatusTag({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  const tone =
    normalized === 'available' || normalized === 'no_damage' || normalized === 'resolved' || normalized === 'closed'
      ? 'success'
      : normalized === 'booked' || normalized === 'in_use' || normalized === 'pending' || normalized === 'started' || normalized === 'ops'
        ? 'info'
        : 'warning'
  return <span className={`customer-status-tag customer-status-tag--${tone}`}>{formatSeverityLabel(status)}</span>
}

function joinMeta(parts: Array<string | null | undefined>) {
  return parts.filter(Boolean).join(' - ')
}

function displayVehicleLabel(vehicle: Pick<Vehicle, 'id' | 'model' | 'stationName' | 'zone'>) {
  return joinMeta([vehicle.model, vehicle.stationName ?? vehicle.zone, `Vehicle ${vehicle.id}`])
}

function displayBookingLabel(booking: Pick<Booking, 'bookingId' | 'bookingCode' | 'customerName' | 'vehicleName' | 'pickupLocation'>) {
  return joinMeta([
    booking.bookingCode ?? `Booking #${booking.bookingId}`,
    booking.customerName ?? null,
    booking.vehicleName ?? null,
    booking.pickupLocation ?? null,
  ])
}

function evidenceSummary(record: Pick<RecordItem, 'evidenceCount' | 'evidenceUrls'>) {
  const count = record.evidenceCount ?? record.evidenceUrls?.length ?? 0
  return count > 0 ? `${count} image${count === 1 ? '' : 's'}` : 'No images'
}

function disruptionNotificationMeta(notification: Notification) {
  const payload = notification.payload
  if (!payload) return null
  const primaryBookingCancelled = payload.primaryBookingCancelled === true
  const futureBookingsCancelledCount =
    typeof payload.futureBookingsCancelledCount === 'number' ? payload.futureBookingsCancelledCount : null
  if (!primaryBookingCancelled && !futureBookingsCancelledCount) {
    return null
  }
  return {
    primaryBookingCancelled,
    futureBookingsCancelledCount: futureBookingsCancelledCount ?? 0,
  }
}

export function OpsPage({
  activeUserId,
  onCustomerDataChanged,
}: {
  activeUserId: string
  onCustomerDataChanged: () => Promise<void>
}) {
  const vehicleStatuses = ['AVAILABLE', 'BOOKED', 'IN_USE', 'UNDER_INSPECTION', 'MAINTENANCE_REQUIRED'] as const
  const [activeSection, setActiveSection] = useState<OpsSection>('fleet')
  const [status, setStatus] = useState('Operations dashboard ready.')
  const [busy, setBusy] = useState(false)
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [vehicleStatusDrafts, setVehicleStatusDrafts] = useState<Record<number, string>>({})
  const [customers, setCustomers] = useState<CustomerSummary[]>([])
  const [bookings, setBookings] = useState<Booking[]>([])
  const [trips, setTrips] = useState<Trip[]>([])
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [records, setRecords] = useState<RecordItem[]>([])
  const [reviewQueue, setReviewQueue] = useState<RecordItem[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [fleetSearch, setFleetSearch] = useState('')
  const [selectedTicketId, setSelectedTicketId] = useState<number | null>(null)
  const [ticketDetail, setTicketDetail] = useState<OpsTicketDetailResponse | null>(null)
  const [ticketDetailBusy, setTicketDetailBusy] = useState(false)
  const [telemetryForm, setTelemetryForm] = useState({
    vehicleId: '2',
    batteryLevel: '14',
    tirePressureOk: false,
    severity: 'CRITICAL',
    faultCode: 'LOW_BATTERY',
  })
  const [renewalUserId, setRenewalUserId] = useState(activeUserId || 'user-1001')

  async function refresh() {
    const dashboard = await opsFetchJson<OpsDashboardResponse>('/ops-console/dashboard')
    startTransition(() => {
      setVehicles(dashboard.vehicles)
      setVehicleStatusDrafts(Object.fromEntries(dashboard.vehicles.map((vehicle) => [vehicle.id, vehicle.status])))
      setCustomers(dashboard.customers)
      setBookings(dashboard.bookings)
      setTrips(dashboard.trips)
      setTickets(dashboard.tickets)
      setRecords(dashboard.records)
      setReviewQueue(dashboard.reviewQueue)
      setPayments(dashboard.payments)
      setNotifications(dashboard.notifications)
    })
  }

  async function openTicketDetail(ticketId: number) {
    setSelectedTicketId(ticketId)
    setTicketDetailBusy(true)
    try {
      const detail = await opsFetchJson<OpsTicketDetailResponse>(`/ops-console/tickets/${ticketId}`)
      startTransition(() => {
        setTicketDetail(detail)
      })
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unable to load ticket detail.')
    } finally {
      setTicketDetailBusy(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    setBusy(true)
    refresh()
      .then(() => {
        if (!cancelled) {
          setStatus('Operations dashboard synced.')
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : 'Unable to refresh operations dashboard.')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setBusy(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function runAction(action: () => Promise<void>, successMessage: string) {
    setBusy(true)
    try {
      await action()
      await Promise.all([refresh(), onCustomerDataChanged()])
      setStatus(successMessage)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unexpected operations error.')
    } finally {
      setBusy(false)
    }
  }

  const unavailableVehicles = useMemo(() => vehicles.filter((vehicle) => vehicle.status !== 'AVAILABLE'), [vehicles])
  const fleetSearchQuery = fleetSearch.trim().toLowerCase()
  const filteredVehicles = useMemo(() => {
    if (!fleetSearchQuery) {
      return vehicles
    }
    return vehicles.filter((vehicle) =>
      [
        String(vehicle.id),
        vehicle.model,
        vehicle.stationName,
        vehicle.stationAddress,
        vehicle.zone,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(fleetSearchQuery)),
    )
  }, [fleetSearchQuery, vehicles])
  const filteredUnavailableVehicles = useMemo(
    () => filteredVehicles.filter((vehicle) => vehicle.status !== 'AVAILABLE'),
    [filteredVehicles],
  )
  const activeTrips = useMemo(() => trips.filter((trip) => trip.status === 'STARTED'), [trips])
  const openTickets = useMemo(() => tickets.filter((ticket) => ticket.status !== 'RESOLVED' && ticket.status !== 'CLOSED'), [tickets])
  const opsNotifications = useMemo(
    () => notifications.filter((notification) => notification.audience === 'OPS' || notification.userId.toLowerCase().startsWith('ops')),
    [notifications],
  )
  const disruptedBookings = useMemo(() => bookings.filter((booking) => booking.status === 'CANCELLED' || booking.status === 'DISRUPTED'), [bookings])
  const latestPayments = useMemo(() => [...payments].sort((left, right) => right.paymentId - left.paymentId).slice(0, 10), [payments])
  const latestRecords = useMemo(() => [...records].sort((left, right) => right.recordId - left.recordId).slice(0, 10), [records])
  const latestNotifications = useMemo(() => [...opsNotifications].sort((left, right) => right.notificationId - left.notificationId).slice(0, 12), [opsNotifications])
  const refundPayments = useMemo(() => payments.filter((payment) => payment.status === 'REFUNDED'), [payments])
  const adjustmentPayments = useMemo(() => payments.filter((payment) => payment.status === 'ADJUSTED'), [payments])
  const customerOptions = useMemo(
    () => customers.filter((customer) => customer.role === 'CUSTOMER').map((customer) => customer.userId).sort(),
    [customers],
  )

  useEffect(() => {
    if (customerOptions.length > 0 && !customerOptions.includes(renewalUserId)) {
      setRenewalUserId(customerOptions[0])
    }
  }, [customerOptions, renewalUserId])

  useEffect(() => {
    if (selectedTicketId === null) {
      setTicketDetail(null)
      return
    }
    if (!tickets.some((ticket) => ticket.ticketId === selectedTicketId)) {
      setSelectedTicketId(null)
      setTicketDetail(null)
    }
  }, [selectedTicketId, tickets])

  useEffect(() => {
    const vehicleIds = vehicles.map((vehicle) => String(vehicle.id))
    if (vehicleIds.length > 0 && !vehicleIds.includes(telemetryForm.vehicleId)) {
      setTelemetryForm((current) => ({ ...current, vehicleId: vehicleIds[0] }))
    }
  }, [telemetryForm.vehicleId, vehicles])

  const sectionCopy: Record<OpsSection, { eyebrow: string; title: string; subtitle: string }> = {
    fleet: {
      eyebrow: 'Fleet',
      title: 'Fleet control',
      subtitle: 'Vehicle health, availability, and shift-wide pressure in one mobile operations surface.',
    },
    tickets: {
      eyebrow: 'Tickets',
      title: 'Incident desk',
      subtitle: 'Maintenance tickets, manual reviews, evidence, and booking impact grouped together.',
    },
    inbox: {
      eyebrow: 'Inbox',
      title: 'Ops inbox',
      subtitle: 'Operational alerts and customer-impact notifications in a single feed.',
    },
    actions: {
      eyebrow: 'Actions',
      title: 'Intervention tools',
      subtitle: 'Run high-friction operational actions without leaving the mobile shell.',
    },
    billing: {
      eyebrow: 'Billing',
      title: 'Billing watch',
      subtitle: 'Refunds, adjustments, trip outcomes, and reservation-side financial impact for ops follow-up.',
    },
  }

  return (
    <div className="customer-mobile-shell app-shell ops-mobile-shell">
      <div className="customer-mobile-shell__chrome ops-mobile-shell__chrome">
        <div className="customer-mobile-statusbar">
          <span>{deviceTime()}</span>
          <span>{busy ? 'Syncing' : 'Operations'}</span>
        </div>
        <div className="customer-mobile-titlebar">
          <span>Ops</span>
          <small>FLEETSHARE CONTROL</small>
        </div>
      </div>

      <main className="customer-mobile-content ops-mobile-content">
        <div className="customer-page-stack">
          <OpsSectionHeader {...sectionCopy[activeSection]} />

          {activeSection === 'fleet' ? (
            <>
              <section className="customer-hero-card customer-hero-card--blue ops-mobile-hero">
                <div>
                  <p className="customer-page-header__eyebrow">Current shift</p>
                  <h2>Fleet health at a glance</h2>
                  <p>Start here for the highest-signal operational metrics before moving into tickets or actions.</p>
                </div>
                <div className="customer-stat-grid">
                  <OpsMetricCard label="Fleet size" value={vehicles.length} />
                  <OpsMetricCard label="Unavailable" value={unavailableVehicles.length} />
                  <OpsMetricCard label="Active trips" value={activeTrips.length} />
                  <OpsMetricCard label="Open tickets" value={openTickets.length} />
                </div>
              </section>

              <article className={`customer-card ${busy ? 'customer-card--warning' : 'customer-card--info'}`}>
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Shift status</p>
                    <h2>Operations pulse</h2>
                  </div>
                  <span className={`customer-status-pill ${busy ? 'customer-status-pill--busy' : ''}`}>{busy ? 'Syncing' : 'Live'}</span>
                </div>
                <p>{status}</p>
                <div className="customer-action-row">
                  <button className="customer-button customer-button--secondary" onClick={() => setActiveSection('actions')} type="button">
                    Open actions
                  </button>
                  <button className="customer-button customer-button--ghost" onClick={() => setActiveSection('inbox')} type="button">
                    Check inbox
                  </button>
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Search</p>
                    <h2>Find a vehicle fast</h2>
                  </div>
                </div>
                <div className="customer-form-stack">
                  <label>
                    Search by vehicle ID, model, station, or zone
                    <input
                      placeholder="2, Kona, Pasir Ris, East"
                      type="search"
                      value={fleetSearch}
                      onChange={(event) => setFleetSearch(event.target.value)}
                    />
                  </label>
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Attention needed</p>
                    <h2>Fleet pressure</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {filteredUnavailableVehicles.slice(0, 6).map((vehicle) => (
                    <article className="customer-list-card" key={vehicle.id}>
                      <div className="customer-card__header">
                        <div>
                          <strong>{vehicle.model}</strong>
                          <p>{joinMeta([vehicle.stationName ?? vehicle.zone, `Vehicle ${vehicle.id}`])}</p>
                        </div>
                        <OpsStatusTag status={vehicle.status} />
                      </div>
                    </article>
                  ))}
                  {filteredUnavailableVehicles.length === 0 ? <p className="customer-empty-copy">No vehicles match this search with an active issue.</p> : null}
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Vehicle control</p>
                    <h2>Apply status updates</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {filteredVehicles.map((vehicle) => (
                    <article className="customer-list-card ops-mobile-list-card" key={vehicle.id}>
                      <div className="customer-card__header">
                        <div>
                          <strong>{vehicle.model}</strong>
                          <p>{joinMeta([vehicle.stationName ?? vehicle.zone, `Vehicle ${vehicle.id}`])}</p>
                        </div>
                        <OpsStatusTag status={vehicle.status} />
                      </div>
                      <div className="customer-form-stack">
                        <label>
                          Status
                          <select
                            value={vehicleStatusDrafts[vehicle.id] ?? vehicle.status}
                            onChange={(event) =>
                              setVehicleStatusDrafts((current) => ({
                                ...current,
                                [vehicle.id]: event.target.value,
                              }))
                            }
                          >
                            {vehicleStatuses.map((vehicleStatus) => (
                              <option key={vehicleStatus} value={vehicleStatus}>
                                {vehicleStatus}
                              </option>
                            ))}
                          </select>
                        </label>
                        <button
                          className="customer-button customer-button--primary"
                          onClick={() =>
                            void runAction(async () => {
                              await opsFetchJson(`/ops-console/fleet/${vehicle.id}/status`, {
                                method: 'PATCH',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                  status: vehicleStatusDrafts[vehicle.id] ?? vehicle.status,
                                }),
                              })
                            }, `Vehicle ${vehicle.id} status updated to ${vehicleStatusDrafts[vehicle.id] ?? vehicle.status}.`)
                          }
                          type="button"
                        >
                          Apply status
                        </button>
                      </div>
                    </article>
                  ))}
                  {filteredVehicles.length === 0 ? <p className="customer-empty-copy">No vehicles matched the current search.</p> : null}
                </div>
              </article>
            </>
          ) : null}

          {activeSection === 'tickets' ? (
            <>
              <section className="customer-hero-card customer-hero-card--blue ops-mobile-hero">
                <div>
                  <p className="customer-page-header__eyebrow">Incident summary</p>
                  <h2>Tickets and reviews</h2>
                  <p>Maintenance work, customer impact, and evidence review stay grouped here for faster triage.</p>
                </div>
                <div className="customer-stat-grid">
                  <OpsMetricCard label="Open tickets" value={openTickets.length} />
                  <OpsMetricCard label="Review queue" value={reviewQueue.length} />
                  <OpsMetricCard label="Disrupted" value={disruptedBookings.length} />
                  <OpsMetricCard label="Records" value={latestRecords.length} />
                </div>
              </section>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Maintenance</p>
                    <h2>Open tickets</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {tickets.map((ticket) => (
                    <article className="customer-list-card" key={ticket.ticketId}>
                      <div className="customer-card__header">
                        <div>
                          <strong>{ticket.vehicleName ?? `Ticket #${ticket.ticketId}`}</strong>
                          <p>{joinMeta([`Ticket #${ticket.ticketId}`, ticket.customerName ?? ticket.userId, ticket.damageType, ticket.stationName ?? ticket.zone])}</p>
                        </div>
                        <OpsStatusTag status={ticket.damageSeverity} />
                      </div>
                      <div className="customer-keyvalue-list">
                        <div className="customer-keyvalue-row">
                          <span>Status</span>
                          <strong>{formatSeverityLabel(ticket.status)}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Created</span>
                          <strong>{formatDateTime(ticket.createdAt)}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Evidence</span>
                          <strong>{ticket.hasEvidence ? `${ticket.evidenceCount ?? 0} attached` : 'None'}</strong>
                        </div>
                      </div>
                      <div className="customer-action-row">
                        <button className="customer-button customer-button--secondary" onClick={() => void openTicketDetail(ticket.ticketId)} type="button">
                          Open detail
                        </button>
                      </div>
                    </article>
                  ))}
                  {tickets.length === 0 ? <p className="customer-empty-copy">No maintenance tickets recorded.</p> : null}
                </div>
              </article>

              {selectedTicketId ? (
                <article className={`customer-card ${ticketDetail?.ticket.hasEvidence ? 'customer-card--info' : ''}`}>
                  <div className="customer-card__header">
                    <div>
                      <p className="customer-page-header__eyebrow">Ticket detail</p>
                      <h2>{ticketDetail?.ticket.vehicleName ?? `Ticket #${selectedTicketId}`}</h2>
                    </div>
                    <button className="customer-button customer-button--ghost" onClick={() => setSelectedTicketId(null)} type="button">
                      Close
                    </button>
                  </div>
                  {ticketDetailBusy || !ticketDetail || ticketDetail.ticket.ticketId !== selectedTicketId ? (
                    <p>Loading ticket detail...</p>
                  ) : (
                    <>
                      <div className="customer-keyvalue-list">
                        <div className="customer-keyvalue-row">
                          <span>Severity</span>
                          <strong>{formatSeverityLabel(ticketDetail.ticket.damageSeverity)}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Status</span>
                          <strong>{formatSeverityLabel(ticketDetail.ticket.status)}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Created</span>
                          <strong>{formatDateTime(ticketDetail.ticket.createdAt)}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Recommended action</span>
                          <strong>{ticketDetail.ticket.recommendedAction ?? 'Inspect and resolve'}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Booking</span>
                          <strong>{ticketDetail.booking ? displayBookingLabel(ticketDetail.booking) : ticketDetail.ticket.bookingCode ?? 'Not linked'}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Trip</span>
                          <strong>{ticketDetail.trip?.tripId ? `Trip #${ticketDetail.trip.tripId}` : 'Not linked'}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Vehicle</span>
                          <strong>{ticketDetail.vehicle ? displayVehicleLabel(ticketDetail.vehicle) : ticketDetail.ticket.vehicleName ?? `Vehicle ${ticketDetail.ticket.vehicleId}`}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Customer</span>
                          <strong>{ticketDetail.customer?.displayName ?? ticketDetail.ticket.customerName ?? ticketDetail.ticket.userId ?? 'Ops only'}</strong>
                        </div>
                        <div className="customer-keyvalue-row">
                          <span>Estimated duration</span>
                          <strong>{formatHours(ticketDetail.ticket.estimatedDurationHours)}</strong>
                        </div>
                      </div>
                      {ticketDetail.record ? (
                        <>
                          <p className="customer-inline-notice">
                            {ticketDetail.record.notes ?? ticketDetail.ticket.recordSummary ?? 'No inspection notes were saved for this record.'}
                          </p>
                          {ticketDetail.evidenceUrls.length > 0 ? (
                            <div className="customer-list-stack">
                              {ticketDetail.evidenceUrls.map((url, index) => (
                                <a className="customer-button customer-button--ghost link-button" href={url} key={`${url}-${index}`} rel="noreferrer" target="_blank">
                                  Open evidence image {index + 1}
                                </a>
                              ))}
                            </div>
                          ) : null}
                        </>
                      ) : (
                        <p className="customer-empty-copy">No linked inspection record was available for this ticket.</p>
                      )}
                    </>
                  )}
                </article>
              ) : null}

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Manual review</p>
                    <h2>Review queue</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {reviewQueue.map((record) => (
                    <article className="customer-list-card" key={record.recordId}>
                      <div className="customer-card__header">
                        <div>
                          <strong>{record.vehicleName ?? `Record #${record.recordId}`}</strong>
                          <p>{joinMeta([`Record #${record.recordId}`, record.customerName ?? record.userId, record.recordType, evidenceSummary(record)])}</p>
                        </div>
                        <OpsStatusTag status={record.severity} />
                      </div>
                      <p>{formatDateTime(record.createdAt)}</p>
                    </article>
                  ))}
                  {reviewQueue.length === 0 ? <p className="customer-empty-copy">No manual review items.</p> : null}
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Customer impact</p>
                    <h2>Disrupted bookings</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {disruptedBookings.slice(0, 10).map((booking) => (
                    <article className="customer-list-card" key={booking.bookingId}>
                      <div className="customer-card__header">
                        <div>
                          <strong>{booking.customerName ?? booking.userId}</strong>
                          <p>{displayBookingLabel(booking)}</p>
                        </div>
                        <OpsStatusTag status={booking.status} />
                      </div>
                      <p>{joinMeta([formatDateTime(booking.startTime), formatDateTime(booking.endTime)])}</p>
                    </article>
                  ))}
                  {disruptedBookings.length === 0 ? <p className="customer-empty-copy">No disrupted bookings right now.</p> : null}
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Evidence</p>
                    <h2>Latest records</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {latestRecords.map((record) => (
                    <article className="customer-list-card" key={record.recordId}>
                      <div className="customer-card__header">
                        <div>
                          <strong>{record.vehicleName ?? `Record #${record.recordId}`}</strong>
                          <p>{joinMeta([`Record #${record.recordId}`, record.customerName ?? record.userId, record.recordType, formatSeverityLabel(record.reviewState)])}</p>
                        </div>
                        <OpsStatusTag status={record.severity} />
                      </div>
                      <p>{joinMeta([formatDateTime(record.createdAt), evidenceSummary(record)])}</p>
                    </article>
                  ))}
                  {latestRecords.length === 0 ? <p className="customer-empty-copy">No evidence records yet.</p> : null}
                </div>
              </article>
            </>
          ) : null}

          {activeSection === 'inbox' ? (
            <>
              <section className="customer-hero-card customer-hero-card--blue ops-mobile-hero">
                <div>
                  <p className="customer-page-header__eyebrow">Alerts</p>
                  <h2>Operations inbox</h2>
                  <p>Use this feed for what changed most recently and which incidents need acknowledgment first.</p>
                </div>
                <div className="customer-stat-grid">
                  <OpsMetricCard label="Alerts" value={opsNotifications.length} />
                  <OpsMetricCard label="Open tickets" value={openTickets.length} />
                  <OpsMetricCard label="Review queue" value={reviewQueue.length} />
                  <OpsMetricCard label="Refunds" value={refundPayments.length} />
                </div>
              </section>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Notification feed</p>
                    <h2>Latest alerts</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {latestNotifications.map((notification) => {
                    const disruptionMeta = disruptionNotificationMeta(notification)
                    return (
                      <article className="customer-transaction-card" key={notification.notificationId}>
                        <div className="customer-transaction-card__top">
                          <div>
                            <p className="customer-transaction-card__eyebrow">{notification.audience}</p>
                            <strong>{notification.subject}</strong>
                          </div>
                          <OpsStatusTag status={notification.severity ?? notification.audience} />
                        </div>
                        <p className="customer-transaction-card__detail">{notification.message}</p>
                        <p className="customer-transaction-card__subtitle">
                          {joinMeta([
                            notification.customerName ?? notification.userId,
                            notification.vehicleName ?? (notification.vehicleId ? `Vehicle ${notification.vehicleId}` : null),
                            notification.bookingCode ?? (notification.bookingId ? `Booking #${notification.bookingId}` : null),
                          ])}
                        </p>
                        <div className="customer-pill-row">
                          <span className="customer-status-tag">{formatDateTime(notification.createdAt)}</span>
                          {notification.tripId ? <span className="customer-status-tag">Trip #{notification.tripId}</span> : null}
                          {notification.stationName ? <span className="customer-status-tag">{notification.stationName}</span> : null}
                          {disruptionMeta?.primaryBookingCancelled ? <span className="customer-status-tag">Booking cancelled</span> : null}
                          {(disruptionMeta?.futureBookingsCancelledCount ?? 0) > 0 ? (
                            <span className="customer-status-tag">
                              {disruptionMeta?.futureBookingsCancelledCount} future bookings also cancelled
                            </span>
                          ) : null}
                        </div>
                      </article>
                    )
                  })}
                  {latestNotifications.length === 0 ? <p className="customer-empty-copy">No operations notifications yet.</p> : null}
                </div>
              </article>
            </>
          ) : null}

          {activeSection === 'actions' ? (
            <>
              <section className="customer-hero-card customer-hero-card--blue ops-mobile-hero">
                <div>
                  <p className="customer-page-header__eyebrow">Control tools</p>
                  <h2>Operator actions</h2>
                  <p>Write actions stay isolated here so the rest of the ops console remains read-focused and easier to scan.</p>
                </div>
                <div className="customer-stat-grid">
                  <OpsMetricCard label="Target vehicles" value={vehicles.length} />
                  <OpsMetricCard label="Customers" value={customerOptions.length} />
                  <OpsMetricCard label="Busy state" value={busy ? 'SYNCING' : 'READY'} />
                  <OpsMetricCard label="Ops inbox" value={opsNotifications.length} />
                </div>
              </section>

              <article className={`customer-card ${busy ? 'customer-card--warning' : 'customer-card--info'}`}>
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Live status</p>
                    <h2>Operational guidance</h2>
                  </div>
                  <span className={`customer-status-pill ${busy ? 'customer-status-pill--busy' : ''}`}>{busy ? 'Syncing' : 'Ready'}</span>
                </div>
                <p>{status}</p>
                <div className="customer-action-row">
                  <Link className="customer-button customer-button--secondary link-button" to={activeUserId ? '/app/home' : '/'}>
                    Back to customer app
                  </Link>
                  <button className="customer-button customer-button--ghost" onClick={() => setActiveSection('tickets')} type="button">
                    Review tickets
                  </button>
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Telemetry injection</p>
                    <h2>Trigger vehicle fault flow</h2>
                  </div>
                </div>
                <div className="customer-form-stack">
                  <label>
                    Vehicle ID
                    <select value={telemetryForm.vehicleId} onChange={(event) => setTelemetryForm((current) => ({ ...current, vehicleId: event.target.value }))}>
                      {vehicles.map((vehicle) => (
                        <option key={vehicle.id} value={String(vehicle.id)}>
                          {vehicle.id} - {vehicle.model}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Battery
                    <input value={telemetryForm.batteryLevel} onChange={(event) => setTelemetryForm((current) => ({ ...current, batteryLevel: event.target.value }))} />
                  </label>
                  <label>
                    Severity
                    <select value={telemetryForm.severity} onChange={(event) => setTelemetryForm((current) => ({ ...current, severity: event.target.value }))}>
                      <option value="INFO">INFO</option>
                      <option value="WARNING">WARNING</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                  </label>
                  <label>
                    Fault code
                    <input value={telemetryForm.faultCode} onChange={(event) => setTelemetryForm((current) => ({ ...current, faultCode: event.target.value }))} />
                  </label>
                  <label className="ops-mobile-toggle">
                    <input
                      checked={telemetryForm.tirePressureOk}
                      onChange={(event) => setTelemetryForm((current) => ({ ...current, tirePressureOk: event.target.checked }))}
                      type="checkbox"
                    />
                    <span>Tire pressure OK</span>
                  </label>
                  <button
                    className="customer-button customer-button--primary"
                    onClick={() =>
                      void runAction(async () => {
                        await opsFetchJson('/ops-console/fleet/telemetry', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({
                            vehicleId: Number(telemetryForm.vehicleId),
                            batteryLevel: Number(telemetryForm.batteryLevel),
                            tirePressureOk: telemetryForm.tirePressureOk,
                            severity: telemetryForm.severity,
                            faultCode: telemetryForm.faultCode,
                          }),
                        })
                      }, `Telemetry injected for vehicle ${telemetryForm.vehicleId}.`)
                    }
                    type="button"
                  >
                    Inject telemetry
                  </button>
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Renewal simulation</p>
                    <h2>Publish reconciliation event</h2>
                  </div>
                </div>
                <div className="customer-form-stack">
                  <label>
                    Customer user ID
                    <select value={renewalUserId} onChange={(event) => setRenewalUserId(event.target.value)}>
                      {customerOptions.map((userId) => (
                        <option key={userId} value={userId}>
                          {userId}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="customer-button customer-button--primary"
                    onClick={() =>
                      void runAction(async () => {
                        await opsFetchJson('/ops-console/renewal/simulate', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ userId: renewalUserId }),
                        })
                      }, `Renewal event published for ${renewalUserId}.`)
                    }
                    type="button"
                  >
                    Simulate renewal
                  </button>
                </div>
              </article>
            </>
          ) : null}

          {activeSection === 'billing' ? (
            <>
              <section className="customer-hero-card customer-hero-card--blue ops-mobile-hero">
                <div>
                  <p className="customer-page-header__eyebrow">Settlement watch</p>
                  <h2>Billing flow</h2>
                  <p>Use this section to track refunds, adjustments, trip outcomes, and reservation-side financial impact.</p>
                </div>
                <div className="customer-stat-grid">
                  <OpsMetricCard label="Payments" value={payments.length} />
                  <OpsMetricCard label="Refunds" value={refundPayments.length} />
                  <OpsMetricCard label="Credits" value={adjustmentPayments.length} />
                  <OpsMetricCard label="Bookings" value={bookings.length} />
                </div>
              </section>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Payments</p>
                    <h2>Recent adjustments and charges</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {latestPayments.map((payment) => (
                    <article className="customer-transaction-card" key={payment.paymentId}>
                      <div className="customer-transaction-card__top">
                        <div>
                          <p className="customer-transaction-card__eyebrow">{payment.status}</p>
                          <strong>{payment.reason.replaceAll('_', ' ')}</strong>
                        </div>
                        <strong className={`customer-transaction-amount customer-transaction-amount--${payment.status === 'REFUNDED' || payment.status === 'ADJUSTED' ? 'credit' : 'debit'}`}>
                          {formatMoney(payment.amount)}
                        </strong>
                      </div>
                      <p className="customer-transaction-card__detail">
                        {joinMeta([payment.bookingId ? `Booking #${payment.bookingId}` : null, payment.tripId ? `Trip #${payment.tripId}` : null, formatDateTime(payment.createdAt)])}
                      </p>
                    </article>
                  ))}
                  {latestPayments.length === 0 ? <p className="customer-empty-copy">No payment records yet.</p> : null}
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Trips</p>
                    <h2>Trip outcomes</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {trips.slice(0, 10).map((trip) => (
                    <article className="customer-list-card" key={trip.tripId}>
                      <div className="customer-card__header">
                        <div>
                          <strong>Trip #{trip.tripId}</strong>
                          <p>{joinMeta([trip.bookingId ? `Booking #${trip.bookingId}` : null, trip.vehicleId ? `Vehicle ${trip.vehicleId}` : null, formatDateTime(trip.startedAt)])}</p>
                        </div>
                        <strong>{formatHours(trip.durationHours)}</strong>
                      </div>
                    </article>
                  ))}
                  {trips.length === 0 ? <p className="customer-empty-copy">No trip outcomes to display.</p> : null}
                </div>
              </article>

              <article className="customer-card">
                <div className="customer-card__header">
                  <div>
                    <p className="customer-page-header__eyebrow">Bookings</p>
                    <h2>Reservation ledger</h2>
                  </div>
                </div>
                <div className="customer-list-stack">
                  {bookings.slice(0, 12).map((booking) => (
                    <article className="customer-list-card" key={booking.bookingId}>
                      <div className="customer-card__header">
                        <div>
                          <strong>Booking #{booking.bookingId}</strong>
                          <p>{displayBookingLabel(booking)}</p>
                        </div>
                        <OpsStatusTag status={booking.status} />
                      </div>
                    </article>
                  ))}
                  {bookings.length === 0 ? <p className="customer-empty-copy">No reservation ledger entries yet.</p> : null}
                </div>
              </article>
            </>
          ) : null}
        </div>
      </main>

      <nav className="ops-mobile-bottomnav">
        <OpsNavButton active={activeSection === 'fleet'} icon={<FleetIcon />} label="Fleet" onClick={() => setActiveSection('fleet')} />
        <OpsNavButton active={activeSection === 'tickets'} count={openTickets.length + reviewQueue.length} icon={<TicketsIcon />} label="Tickets" onClick={() => setActiveSection('tickets')} />
        <OpsNavButton active={activeSection === 'inbox'} count={opsNotifications.length} icon={<InboxIcon />} label="Inbox" onClick={() => setActiveSection('inbox')} />
        <OpsNavButton active={activeSection === 'actions'} icon={<ActionsIcon />} label="Actions" onClick={() => setActiveSection('actions')} />
        <OpsNavButton active={activeSection === 'billing'} icon={<BillingIcon />} label="Billing" onClick={() => setActiveSection('billing')} />
      </nav>
    </div>
  )
}
