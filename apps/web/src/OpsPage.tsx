import { startTransition, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  fetchJson,
  formatHours,
  formatMoney,
  formatSeverityLabel,
} from './appTypes'
import type { Booking, CustomerSummary, Notification, Payment, RecordItem, Ticket, Trip, Vehicle } from './appTypes'

type OpsTab = 'overview' | 'fleet' | 'incidents' | 'billing' | 'inbox'

function BellIcon() {
  return (
    <svg aria-hidden="true" className="ops-bell-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M15 18H5.5a1 1 0 0 1-.8-1.6l1.4-1.9a5 5 0 0 0 1-3V9a5 5 0 1 1 10 0v2.5a5 5 0 0 0 1 3l1.4 1.9a1 1 0 0 1-.8 1.6H15Z" />
      <path d="M9.5 18a2.5 2.5 0 0 0 5 0" />
    </svg>
  )
}

function OpsTabButton({
  active,
  count,
  label,
  onClick,
}: {
  active: boolean
  count?: number
  label: string
  onClick: () => void
}) {
  return (
    <button className={`ops-tab ${active ? 'ops-tab--active' : ''}`} onClick={onClick} type="button">
      <span>{label}</span>
      {count !== undefined ? <small className="ops-tab__count">{count}</small> : null}
    </button>
  )
}

function MetricCard({
  label,
  value,
  tone = 'neutral',
}: {
  label: string
  value: string | number
  tone?: 'neutral' | 'attention' | 'good'
}) {
  return (
    <article className={`ops-metric ops-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function VehicleStatusPill({ status }: { status: string }) {
  const normalized = status.toLowerCase()
  const tone =
    normalized === 'available' || normalized === 'no_damage'
      ? 'good'
      : normalized === 'booked' || normalized === 'in_use' || normalized === 'pending'
        ? 'neutral'
        : 'attention'
  return <span className={`ops-status-pill ops-status-pill--${tone}`}>{formatSeverityLabel(status)}</span>
}

export function OpsPage({
  activeUserId,
  onCustomerDataChanged,
}: {
  activeUserId: string
  onCustomerDataChanged: () => Promise<void>
}) {
  const vehicleStatuses = ['AVAILABLE', 'BOOKED', 'IN_USE', 'UNDER_INSPECTION', 'MAINTENANCE_REQUIRED'] as const
  const [activeTab, setActiveTab] = useState<OpsTab>('overview')
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
  const [telemetryForm, setTelemetryForm] = useState({
    vehicleId: '2',
    batteryLevel: '14',
    tirePressureOk: false,
    severity: 'CRITICAL',
    faultCode: 'LOW_BATTERY',
  })
  const [renewalUserId, setRenewalUserId] = useState(activeUserId || 'user-1001')

  async function refresh() {
    const [vehicleData, customerData, bookingData, tripData, ticketData, recordData, queueData, paymentData, notificationData] = await Promise.all([
      fetchJson<Vehicle[]>('/vehicles'),
      fetchJson<CustomerSummary[]>('/pricing/customers'),
      fetchJson<Booking[]>('/bookings'),
      fetchJson<Trip[]>('/trips'),
      fetchJson<Ticket[]>('/maintenance/tickets'),
      fetchJson<RecordItem[]>('/records'),
      fetchJson<RecordItem[]>('/records/manual-review-queue'),
      fetchJson<Payment[]>('/payments'),
      fetchJson<Notification[]>('/notifications'),
    ])
    startTransition(() => {
      setVehicles(vehicleData)
      setVehicleStatusDrafts(Object.fromEntries(vehicleData.map((vehicle) => [vehicle.id, vehicle.status])))
      setCustomers(customerData)
      setBookings(bookingData)
      setTrips(tripData)
      setTickets(ticketData)
      setRecords(recordData)
      setReviewQueue(queueData)
      setPayments(paymentData)
      setNotifications(notificationData)
    })
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

  const unavailableVehicles = useMemo(
    () => vehicles.filter((vehicle) => vehicle.status !== 'AVAILABLE'),
    [vehicles],
  )
  const activeTrips = useMemo(
    () => trips.filter((trip) => trip.status === 'STARTED'),
    [trips],
  )
  const openTickets = useMemo(
    () => tickets.filter((ticket) => ticket.status !== 'RESOLVED' && ticket.status !== 'CLOSED'),
    [tickets],
  )
  const opsNotifications = useMemo(
    () => notifications.filter((notification) => notification.audience === 'OPS' || notification.userId.toLowerCase().startsWith('ops')),
    [notifications],
  )
  const disruptedBookings = useMemo(
    () => bookings.filter((booking) => booking.status === 'CANCELLED' || booking.status === 'DISRUPTED'),
    [bookings],
  )
  const latestPayments = useMemo(
    () => [...payments].sort((left, right) => right.paymentId - left.paymentId).slice(0, 8),
    [payments],
  )
  const latestRecords = useMemo(
    () => [...records].sort((left, right) => right.recordId - left.recordId).slice(0, 8),
    [records],
  )
  const latestNotifications = useMemo(
    () => [...opsNotifications].sort((left, right) => right.notificationId - left.notificationId).slice(0, 10),
    [opsNotifications],
  )
  const customerOptions = useMemo(
    () => customers
      .filter((customer) => customer.role === 'CUSTOMER')
      .map((customer) => customer.userId)
      .sort(),
    [customers],
  )

  useEffect(() => {
    if (customerOptions.length === 0) {
      return
    }
    if (!customerOptions.includes(renewalUserId)) {
      setRenewalUserId(customerOptions[0])
    }
  }, [customerOptions, renewalUserId])

  useEffect(() => {
    const vehicleIds = vehicles.map((vehicle) => String(vehicle.id))
    if (vehicleIds.length === 0) {
      return
    }
    if (!vehicleIds.includes(telemetryForm.vehicleId)) {
      setTelemetryForm((current) => ({ ...current, vehicleId: vehicleIds[0] }))
    }
  }, [telemetryForm.vehicleId, vehicles])

  return (
    <div className="ops-shell ops-shell--dashboard">
      <header className="ops-launchbar">
        <div className="ops-launchbar__title">
          <p className="eyebrow">FleetShare Operations</p>
          <h1>Operations Control Center</h1>
          <p className="hero-copy">
            Monitor fleet health, intervene on incidents, manage availability, and track customer-impacting events from one console.
          </p>
        </div>
        <div className="ops-launchbar__actions">
          <button className="ops-bell-button" onClick={() => setActiveTab('inbox')} type="button">
            <BellIcon />
            <span>Inbox</span>
            <strong>{opsNotifications.length}</strong>
          </button>
          <span className={`status-banner ${busy ? 'status-banner--busy' : ''}`}>{busy ? 'Syncing...' : status}</span>
          <Link className="ghost-link" to={activeUserId ? '/app/home' : '/'}>
            Back to customer app
          </Link>
        </div>
      </header>

      <section className="ops-tabbar">
        <OpsTabButton active={activeTab === 'overview'} label="Overview" onClick={() => setActiveTab('overview')} />
        <OpsTabButton active={activeTab === 'fleet'} count={vehicles.length} label="Fleet" onClick={() => setActiveTab('fleet')} />
        <OpsTabButton active={activeTab === 'incidents'} count={openTickets.length + reviewQueue.length} label="Incidents" onClick={() => setActiveTab('incidents')} />
        <OpsTabButton active={activeTab === 'billing'} count={latestPayments.length} label="Billing" onClick={() => setActiveTab('billing')} />
        <OpsTabButton active={activeTab === 'inbox'} count={opsNotifications.length} label="Inbox" onClick={() => setActiveTab('inbox')} />
      </section>

      {activeTab === 'overview' ? (
        <>
          <section className="ops-metric-grid">
            <MetricCard label="Fleet size" value={vehicles.length} />
            <MetricCard label="Unavailable vehicles" value={unavailableVehicles.length} tone={unavailableVehicles.length ? 'attention' : 'good'} />
            <MetricCard label="Open tickets" value={openTickets.length} tone={openTickets.length ? 'attention' : 'good'} />
            <MetricCard label="Ops inbox" value={opsNotifications.length} />
          </section>

          <section className="panel-card ops-overview-snapshot">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Current shift</p>
                <h2>Operational snapshot</h2>
              </div>
            </div>
            <div className="ops-snapshot-grid">
              <div className="ops-snapshot-pill">
                <span>Active trips</span>
                <strong>{activeTrips.length}</strong>
              </div>
              <div className="ops-snapshot-pill">
                <span>Disrupted bookings</span>
                <strong>{disruptedBookings.length}</strong>
              </div>
              <div className="ops-snapshot-pill">
                <span>Manual review queue</span>
                <strong>{reviewQueue.length}</strong>
              </div>
            </div>
          </section>

          <div className="ops-dashboard-grid">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Quick actions</p>
                <h2>Intervention tools</h2>
              </div>
            </div>
            <div className="ops-quick-grid">
              <section className="ops-quick-card">
                <p className="mini-label">Telemetry injection</p>
                <h3>Trigger vehicle fault flow</h3>
                <div className="form-grid">
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
                  <label className="toggle-line">
                    <input
                      checked={telemetryForm.tirePressureOk}
                      onChange={(event) => setTelemetryForm((current) => ({ ...current, tirePressureOk: event.target.checked }))}
                      type="checkbox"
                    />
                    Tire pressure OK
                  </label>
                </div>
                <button
                  className="primary"
                  onClick={() =>
                    void runAction(async () => {
                      await fetchJson('/vehicles/telemetry', {
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
              </section>

              <section className="ops-quick-card">
                <p className="mini-label">Renewal simulation</p>
                <h3>Publish reconciliation event</h3>
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
                  className="primary"
                  onClick={() =>
                    void runAction(async () => {
                      await fetchJson('/renewal-reconciliation/simulate', {
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
              </section>
            </div>
          </article>

          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Attention needed</p>
                <h2>Current fleet pressure</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {unavailableVehicles.slice(0, 6).map((vehicle) => (
                <div className="ops-list-row" key={vehicle.id}>
                  <div>
                    <strong>{vehicle.model}</strong>
                    <p>{vehicle.zone}</p>
                  </div>
                  <VehicleStatusPill status={vehicle.status} />
                </div>
              ))}
              {unavailableVehicles.length === 0 ? <div className="empty-card"><p>No vehicles need intervention.</p></div> : null}
            </div>
          </article>

          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Ops inbox</p>
                <h2>Latest alerts</h2>
              </div>
              <button className="ghost-link" onClick={() => setActiveTab('inbox')} type="button">
                Open inbox
              </button>
            </div>
            <div className="notification-stack">
              {latestNotifications.slice(0, 4).map((notification) => (
                <article className="notification-card" key={notification.notificationId}>
                  <strong>{notification.subject}</strong>
                  <p>{notification.message}</p>
                </article>
              ))}
              {latestNotifications.length === 0 ? <div className="empty-card"><p>No ops alerts at the moment.</p></div> : null}
            </div>
          </article>

          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Customer impact</p>
                <h2>Disrupted bookings</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {disruptedBookings.slice(0, 6).map((booking) => (
                <div className="ops-list-row" key={booking.bookingId}>
                  <div>
                    <strong>Booking #{booking.bookingId}</strong>
                    <p>{booking.userId} - Vehicle {booking.vehicleId}</p>
                  </div>
                  <VehicleStatusPill status={booking.status} />
                </div>
              ))}
              {disruptedBookings.length === 0 ? <div className="empty-card"><p>No disrupted bookings right now.</p></div> : null}
            </div>
          </article>
          </div>
        </>
      ) : null}

      {activeTab === 'fleet' ? (
        <section className="panel-card">
          <div className="panel-card__header">
            <div>
              <p className="mini-label">Fleet management</p>
              <h2>Vehicle availability and status control</h2>
            </div>
          </div>
          <div className="ops-vehicle-grid">
            {vehicles.map((vehicle) => (
              <article className="ops-vehicle-card" key={vehicle.id}>
                <div className="ops-vehicle-card__top">
                  <div>
                    <p className="mini-label">Vehicle {vehicle.id}</p>
                    <h3>{vehicle.model}</h3>
                    <p>{vehicle.zone}</p>
                  </div>
                  <VehicleStatusPill status={vehicle.status} />
                </div>
                <div className="ops-vehicle-card__actions">
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
                    className="primary"
                    onClick={() =>
                      void runAction(async () => {
                        await fetchJson(`/vehicles/${vehicle.id}/status`, {
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
          </div>
        </section>
      ) : null}

      {activeTab === 'incidents' ? (
        <div className="ops-dashboard-grid">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Maintenance</p>
                <h2>Open tickets</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {tickets.map((ticket) => (
                <div className="ops-list-row" key={ticket.ticketId}>
                  <div>
                    <strong>Ticket {ticket.ticketId}</strong>
                    <p>Vehicle {ticket.vehicleId} - {ticket.damageType}</p>
                  </div>
                  <VehicleStatusPill status={ticket.damageSeverity} />
                </div>
              ))}
              {tickets.length === 0 ? <div className="empty-card"><p>No maintenance tickets recorded.</p></div> : null}
            </div>
          </article>

          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Manual review</p>
                <h2>Review queue</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {reviewQueue.map((record) => (
                <div className="ops-list-row" key={record.recordId}>
                  <div>
                    <strong>Record {record.recordId}</strong>
                    <p>Vehicle {record.vehicleId} - {record.recordType}</p>
                  </div>
                  <VehicleStatusPill status={record.severity} />
                </div>
              ))}
              {reviewQueue.length === 0 ? <div className="empty-card"><p>No manual review items.</p></div> : null}
            </div>
          </article>

          <article className="panel-card ops-span-wide">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Records</p>
                <h2>Latest evidence and assessments</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {latestRecords.map((record) => (
                <div className="ops-list-row" key={record.recordId}>
                  <div>
                    <strong>Record {record.recordId}</strong>
                    <p>{record.recordType} - Vehicle {record.vehicleId} - {record.reviewState}</p>
                  </div>
                  <VehicleStatusPill status={record.severity} />
                </div>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === 'billing' ? (
        <div className="ops-dashboard-grid">
          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Payments</p>
                <h2>Recent adjustments and charges</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {latestPayments.map((payment) => (
                <div className="ops-list-row" key={payment.paymentId}>
                  <div>
                    <strong>{payment.reason.replaceAll('_', ' ')}</strong>
                    <p>Booking {payment.bookingId ?? 'N/A'} - {payment.status}</p>
                  </div>
                  <strong>{formatMoney(payment.amount)}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="panel-card">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Trips</p>
                <h2>Trip outcomes</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {trips.slice(0, 8).map((trip) => (
                <div className="ops-list-row" key={trip.tripId}>
                  <div>
                    <strong>Trip #{trip.tripId}</strong>
                    <p>Booking {trip.bookingId} - Vehicle {trip.vehicleId}</p>
                  </div>
                  <strong>{formatHours(trip.durationHours)}</strong>
                </div>
              ))}
            </div>
          </article>

          <article className="panel-card ops-span-wide">
            <div className="panel-card__header">
              <div>
                <p className="mini-label">Bookings</p>
                <h2>Reservation ledger</h2>
              </div>
            </div>
            <div className="ops-stack-list">
              {bookings.slice(0, 10).map((booking) => (
                <div className="ops-list-row" key={booking.bookingId}>
                  <div>
                    <strong>Booking #{booking.bookingId}</strong>
                    <p>{booking.userId} - Vehicle {booking.vehicleId} - {booking.pickupLocation}</p>
                  </div>
                  <VehicleStatusPill status={booking.status} />
                </div>
              ))}
            </div>
          </article>
        </div>
      ) : null}

      {activeTab === 'inbox' ? (
        <section className="panel-card">
          <div className="panel-card__header">
            <div>
              <p className="mini-label">Notifications</p>
              <h2>Operations inbox</h2>
            </div>
            <div className="ops-inbox-summary">
              <BellIcon />
              <span>{opsNotifications.length} alerts</span>
            </div>
          </div>
          <div className="notification-stack">
            {latestNotifications.map((notification) => (
              <article className="notification-card" key={notification.notificationId}>
                <div className="panel-card__header">
                  <strong>{notification.subject}</strong>
                  <small>{notification.audience}</small>
                </div>
                <p>{notification.message}</p>
                <small>Booking {notification.bookingId ?? 'N/A'} - Trip {notification.tripId ?? 'N/A'}</small>
              </article>
            ))}
            {latestNotifications.length === 0 ? <div className="empty-card"><p>No operations notifications yet.</p></div> : null}
          </div>
        </section>
      ) : null}
    </div>
  )
}
