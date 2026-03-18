import { startTransition, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  fetchJson,
  formatHours,
  formatMoney,
} from './appTypes'
import type { Booking, Notification, Payment, RecordItem, Ticket, Trip, Vehicle } from './appTypes'

export function OpsPage({
  activeUserId,
  onCustomerDataChanged,
}: {
  activeUserId: string
  onCustomerDataChanged: () => Promise<void>
}) {
  const [status, setStatus] = useState('Ops console ready.')
  const [busy, setBusy] = useState(false)
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
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
    const [vehicleData, bookingData, tripData, ticketData, recordData, queueData, paymentData, notificationData] = await Promise.all([
      fetchJson<Vehicle[]>('/vehicles'),
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
          setStatus('Ops console synced.')
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : 'Unable to refresh ops console.')
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
      setStatus(error instanceof Error ? error.message : 'Unexpected ops error.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ops-shell">
      <header className="ops-header">
        <div>
          <p className="eyebrow">Hidden route</p>
          <h1>FleetShare ops console</h1>
        </div>
        <div className="button-strip">
          <Link className="ghost-link" to={activeUserId ? '/app/home' : '/'}>
            Back to customer app
          </Link>
          <span className={`status-banner ${busy ? 'status-banner--busy' : ''}`}>{busy ? 'Working...' : status}</span>
        </div>
      </header>

      <section className="dashboard-grid">
        <article className="panel-card">
          <p className="mini-label">Telemetry injection</p>
          <h2>Trigger vehicle fault flow</h2>
          <label>
            Vehicle ID
            <input value={telemetryForm.vehicleId} onChange={(event) => setTelemetryForm((current) => ({ ...current, vehicleId: event.target.value }))} />
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
              }, 'Telemetry injected.')
            }
            type="button"
          >
            Inject telemetry
          </button>
        </article>

        <article className="panel-card">
          <p className="mini-label">Renewal demo</p>
          <h2>Publish renewal reconciliation event</h2>
          <label>
            Customer user ID
            <input value={renewalUserId} onChange={(event) => setRenewalUserId(event.target.value)} />
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
              }, 'Renewal event published.')
            }
            type="button"
          >
            Simulate renewal
          </button>
        </article>
      </section>

      <section className="ops-grid">
        <article className="panel-card"><h2>Vehicles</h2><div className="ops-list">{vehicles.map((vehicle) => <p key={vehicle.id}>{vehicle.id} · {vehicle.model} · {vehicle.zone} · {vehicle.status}</p>)}</div></article>
        <article className="panel-card"><h2>Bookings</h2><div className="ops-list">{bookings.map((booking) => <p key={booking.bookingId}>#{booking.bookingId} · {booking.userId} · vehicle {booking.vehicleId} · {booking.status}</p>)}</div></article>
        <article className="panel-card"><h2>Trips</h2><div className="ops-list">{trips.map((trip) => <p key={trip.tripId}>#{trip.tripId} · booking {trip.bookingId} · {trip.status} · {formatHours(trip.durationHours)}</p>)}</div></article>
        <article className="panel-card"><h2>Maintenance</h2><div className="ops-list">{tickets.map((ticket) => <p key={ticket.ticketId}>Ticket {ticket.ticketId} · vehicle {ticket.vehicleId} · {ticket.damageSeverity}</p>)}</div></article>
        <article className="panel-card"><h2>Records</h2><div className="ops-list">{records.map((record) => <p key={record.recordId}>Record {record.recordId} · vehicle {record.vehicleId} · {record.reviewState}</p>)}</div></article>
        <article className="panel-card"><h2>Manual review</h2><div className="ops-list">{reviewQueue.length === 0 ? <p>No manual review items.</p> : reviewQueue.map((record) => <p key={record.recordId}>Record {record.recordId} · {record.severity}</p>)}</div></article>
        <article className="panel-card"><h2>Payments</h2><div className="ops-list">{payments.map((payment) => <p key={payment.paymentId}>Payment {payment.paymentId} · {payment.status} · {formatMoney(payment.amount)}</p>)}</div></article>
        <article className="panel-card"><h2>Notifications</h2><div className="ops-list">{notifications.map((notification) => <p key={notification.notificationId}>{notification.audience} · {notification.subject}</p>)}</div></article>
      </section>
    </div>
  )
}
