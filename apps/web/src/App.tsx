import { startTransition, useEffect, useState } from 'react'
import './App.css'

const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

type Vehicle = {
  id?: number
  vehicleId?: number
  plateNumber: string
  model: string
  zone: string
  vehicleType: string
  status: string
  estimatedPrice?: number
  allowanceStatus?: string
}

type Booking = {
  bookingId: number
  userId: string
  vehicleId: number
  pickupLocation: string
  startTime: string
  endTime: string
  status: string
  displayedPrice: number
  finalPrice: number
  tripId?: number
  reconciliationStatus?: string
  cancellationReason?: string
}

type Trip = {
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

type RecordItem = {
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

type Ticket = {
  ticketId: number
  vehicleId: number
  damageSeverity: string
  damageType: string
  estimatedDurationHours: number
  status: string
}

type Payment = {
  paymentId: number
  bookingId?: number | null
  tripId?: number | null
  userId: string
  amount: number
  reason: string
  status: string
}

type Notification = {
  notificationId: number
  userId: string
  bookingId?: number | null
  tripId?: number | null
  audience: string
  subject: string
  message: string
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, options)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed with ${response.status}`)
  }
  return response.json() as Promise<T>
}

function localDateTime(hoursAhead: number) {
  const date = new Date(Date.now() + hoursAhead * 60 * 60 * 1000)
  const offset = date.getTimezoneOffset()
  return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 16)
}

export default function App() {
  const [activeView, setActiveView] = useState<'customer' | 'operations' | 'technician'>('customer')
  const [status, setStatus] = useState('FleetShare control plane ready.')
  const [busy, setBusy] = useState(false)

  const [searchForm, setSearchForm] = useState({
    userId: 'user-1001',
    pickupLocation: 'SMU',
    vehicleType: 'SUV',
    startTime: localDateTime(1),
    endTime: localDateTime(4),
    subscriptionPlanId: 'STANDARD_MONTHLY',
  })
  const [searchResults, setSearchResults] = useState<Vehicle[]>([])

  const [damageForm, setDamageForm] = useState({
    bookingId: '1',
    vehicleId: '2',
    userId: 'user-1001',
    notes: 'scratch on rear door',
  })
  const [damagePhoto, setDamagePhoto] = useState<File | null>(null)

  const [startTripForm, setStartTripForm] = useState({
    bookingId: '1',
    vehicleId: '2',
    userId: 'user-1001',
    notes: '',
  })
  const [endTripForm, setEndTripForm] = useState({
    tripId: '1',
    bookingId: '1',
    vehicleId: '2',
    userId: 'user-1001',
    endReason: 'USER_COMPLETED',
  })
  const [telemetryForm, setTelemetryForm] = useState({
    vehicleId: '2',
    batteryLevel: '14',
    tirePressureOk: false,
    severity: 'CRITICAL',
    faultCode: 'LOW_BATTERY',
  })
  const [renewalUserId, setRenewalUserId] = useState('user-1001')

  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [bookings, setBookings] = useState<Booking[]>([])
  const [trips, setTrips] = useState<Trip[]>([])
  const [records, setRecords] = useState<RecordItem[]>([])
  const [reviewQueue, setReviewQueue] = useState<RecordItem[]>([])
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])

  async function refreshDashboard() {
    const [vehiclesData, bookingsData, tripsData, recordsData, queueData, ticketData, paymentData, notificationData] =
      await Promise.all([
        fetchJson<Vehicle[]>('/vehicles'),
        fetchJson<Booking[]>('/bookings'),
        fetchJson<Trip[]>('/trips'),
        fetchJson<RecordItem[]>('/records'),
        fetchJson<RecordItem[]>('/records/manual-review-queue'),
        fetchJson<Ticket[]>('/maintenance/tickets'),
        fetchJson<Payment[]>('/payments'),
        fetchJson<Notification[]>('/notifications'),
      ])

    startTransition(() => {
      setVehicles(vehiclesData)
      setBookings(bookingsData)
      setTrips(tripsData)
      setRecords(recordsData)
      setReviewQueue(queueData)
      setTickets(ticketData)
      setPayments(paymentData)
      setNotifications(notificationData)
    })
  }

  async function runAction(action: () => Promise<void>, successMessage: string) {
    setBusy(true)
    try {
      await action()
      await refreshDashboard()
      setStatus(successMessage)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unexpected error')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    setBusy(true)
    refreshDashboard()
      .then(() => {
        if (!cancelled) {
          setStatus('FleetShare dashboard synced.')
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : 'Unexpected error')
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

  async function handleSearch() {
    await runAction(async () => {
      const params = new URLSearchParams({
        startTime: new Date(searchForm.startTime).toISOString(),
        endTime: new Date(searchForm.endTime).toISOString(),
        pickupLocation: searchForm.pickupLocation,
        vehicleType: searchForm.vehicleType,
        subscriptionPlanId: searchForm.subscriptionPlanId,
      })
      const result = await fetchJson<{ vehicleList: Vehicle[] }>(`/search-vehicles/search?${params.toString()}`)
      setSearchResults(result.vehicleList)
    }, 'Vehicle search completed.')
  }

  async function reserveVehicle(vehicleId: number) {
    await runAction(async () => {
      const booking = await fetchJson<{ bookingId: number; finalQuote: number }>(`/process-booking/reserve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userId: searchForm.userId,
          vehicleId,
          pickupLocation: searchForm.pickupLocation,
          startTime: new Date(searchForm.startTime).toISOString(),
          endTime: new Date(searchForm.endTime).toISOString(),
          displayedPrice: 0,
          subscriptionPlanId: searchForm.subscriptionPlanId,
        }),
      })
      setDamageForm((current) => ({ ...current, bookingId: String(booking.bookingId), vehicleId: String(vehicleId), userId: searchForm.userId }))
      setStartTripForm((current) => ({ ...current, bookingId: String(booking.bookingId), vehicleId: String(vehicleId), userId: searchForm.userId }))
      setEndTripForm((current) => ({ ...current, bookingId: String(booking.bookingId), vehicleId: String(vehicleId), userId: searchForm.userId }))
    }, `Booking confirmed for vehicle ${vehicleId}.`)
  }

  async function submitDamageInspection() {
    await runAction(async () => {
      const formData = new FormData()
      formData.append('bookingId', damageForm.bookingId)
      formData.append('vehicleId', damageForm.vehicleId)
      formData.append('userId', damageForm.userId)
      formData.append('notes', damageForm.notes)
      if (damagePhoto) {
        formData.append('photos', damagePhoto)
      }
      await fetchJson('/damage-assessment/external', {
        method: 'POST',
        body: formData,
      })
    }, 'External inspection submitted.')
  }

  async function startTrip() {
    await runAction(async () => {
      const trip = await fetchJson<{ tripId: number }>(`/trips/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bookingId: Number(startTripForm.bookingId),
          vehicleId: Number(startTripForm.vehicleId),
          userId: startTripForm.userId,
          notes: startTripForm.notes,
        }),
      })
      setEndTripForm((current) => ({ ...current, tripId: String(trip.tripId) }))
    }, 'Trip started successfully.')
  }

  async function endTrip() {
    await runAction(async () => {
      await fetchJson('/end-trip/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tripId: Number(endTripForm.tripId),
          bookingId: Number(endTripForm.bookingId),
          vehicleId: Number(endTripForm.vehicleId),
          userId: endTripForm.userId,
          endReason: endTripForm.endReason,
        }),
      })
    }, 'Trip end flow executed.')
  }

  async function sendTelemetry() {
    await runAction(async () => {
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
    }, 'Telemetry injected into vehicle state.')
  }

  async function simulateRenewal() {
    await runAction(async () => {
      await fetchJson('/renewal-reconciliation/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: renewalUserId }),
      })
    }, 'Subscription renewal event published.')
  }

  return (
    <div className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">FleetShare / Smart Car Sharing Control Surface</p>
          <h1>Microservices demo stack for booking, damage, refunds, and proactive maintenance.</h1>
          <p className="lead">
            One UI over Kong, RabbitMQ, gRPC, MySQL, and event-driven recovery flows. Use the customer lane for the
            primary scenarios and the operations lanes to verify fallout, refunds, tickets, and notifications.
          </p>
        </div>
        <div className="status-card">
          <span className={busy ? 'pulse' : ''}>{busy ? 'Processing' : 'Ready'}</span>
          <strong>{status}</strong>
        </div>
      </header>

      <nav className="view-switcher">
        {[
          ['customer', 'Customer Flow'],
          ['operations', 'Operations Control'],
          ['technician', 'Technician Review'],
        ].map(([key, label]) => (
          <button
            key={key}
            className={activeView === key ? 'active' : ''}
            onClick={() => setActiveView(key as typeof activeView)}
            type="button"
          >
            {label}
          </button>
        ))}
      </nav>

      <main className="grid">
        <section className={`panel ${activeView === 'customer' ? 'wide' : ''}`}>
          <h2>Scenario 1: Search and Reserve</h2>
          <div className="form-grid">
            <label>
              User ID
              <input value={searchForm.userId} onChange={(event) => setSearchForm({ ...searchForm, userId: event.target.value })} />
            </label>
            <label>
              Pickup Zone
              <input value={searchForm.pickupLocation} onChange={(event) => setSearchForm({ ...searchForm, pickupLocation: event.target.value })} />
            </label>
            <label>
              Vehicle Type
              <input value={searchForm.vehicleType} onChange={(event) => setSearchForm({ ...searchForm, vehicleType: event.target.value })} />
            </label>
            <label>
              Start Time
              <input type="datetime-local" value={searchForm.startTime} onChange={(event) => setSearchForm({ ...searchForm, startTime: event.target.value })} />
            </label>
            <label>
              End Time
              <input type="datetime-local" value={searchForm.endTime} onChange={(event) => setSearchForm({ ...searchForm, endTime: event.target.value })} />
            </label>
          </div>
          <button className="primary" onClick={handleSearch} type="button">
            Search Vehicles
          </button>
          <div className="collection">
            {searchResults.map((vehicle) => (
              <article key={vehicle.vehicleId} className="card">
                <div>
                  <strong>{vehicle.model}</strong>
                  <p>{vehicle.plateNumber} / {vehicle.zone} / {vehicle.vehicleType}</p>
                </div>
                <div>
                  <p>Quote: SGD {vehicle.estimatedPrice?.toFixed(2)}</p>
                  <p>{vehicle.allowanceStatus}</p>
                </div>
                <button type="button" onClick={() => reserveVehicle(vehicle.vehicleId ?? 0)}>
                  Reserve
                </button>
              </article>
            ))}
          </div>
        </section>

        <section className="panel">
          <h2>Scenario 2: Pre-Trip Damage Check</h2>
          <div className="form-grid">
            <label>
              Booking ID
              <input value={damageForm.bookingId} onChange={(event) => setDamageForm({ ...damageForm, bookingId: event.target.value })} />
            </label>
            <label>
              Vehicle ID
              <input value={damageForm.vehicleId} onChange={(event) => setDamageForm({ ...damageForm, vehicleId: event.target.value })} />
            </label>
            <label>
              User ID
              <input value={damageForm.userId} onChange={(event) => setDamageForm({ ...damageForm, userId: event.target.value })} />
            </label>
            <label className="full">
              Notes
              <textarea value={damageForm.notes} onChange={(event) => setDamageForm({ ...damageForm, notes: event.target.value })} rows={3} />
            </label>
            <label className="full">
              Photo
              <input type="file" accept="image/*" onChange={(event) => setDamagePhoto(event.target.files?.[0] ?? null)} />
            </label>
          </div>
          <button className="primary" onClick={submitDamageInspection} type="button">
            Submit Inspection
          </button>
        </section>

        <section className="panel">
          <h2>Scenario 1/3: Start and End Trip</h2>
          <div className="form-grid">
            <label>
              Booking ID
              <input value={startTripForm.bookingId} onChange={(event) => setStartTripForm({ ...startTripForm, bookingId: event.target.value })} />
            </label>
            <label>
              Vehicle ID
              <input value={startTripForm.vehicleId} onChange={(event) => setStartTripForm({ ...startTripForm, vehicleId: event.target.value })} />
            </label>
            <label>
              User ID
              <input value={startTripForm.userId} onChange={(event) => setStartTripForm({ ...startTripForm, userId: event.target.value })} />
            </label>
            <label className="full">
              Start Notes
              <textarea value={startTripForm.notes} onChange={(event) => setStartTripForm({ ...startTripForm, notes: event.target.value })} rows={2} />
            </label>
          </div>
          <button className="primary" onClick={startTrip} type="button">
            Start Trip
          </button>
          <hr />
          <div className="form-grid">
            <label>
              Trip ID
              <input value={endTripForm.tripId} onChange={(event) => setEndTripForm({ ...endTripForm, tripId: event.target.value })} />
            </label>
            <label>
              Booking ID
              <input value={endTripForm.bookingId} onChange={(event) => setEndTripForm({ ...endTripForm, bookingId: event.target.value })} />
            </label>
            <label>
              Vehicle ID
              <input value={endTripForm.vehicleId} onChange={(event) => setEndTripForm({ ...endTripForm, vehicleId: event.target.value })} />
            </label>
            <label>
              User ID
              <input value={endTripForm.userId} onChange={(event) => setEndTripForm({ ...endTripForm, userId: event.target.value })} />
            </label>
            <label>
              End Reason
              <select value={endTripForm.endReason} onChange={(event) => setEndTripForm({ ...endTripForm, endReason: event.target.value })}>
                <option value="USER_COMPLETED">USER_COMPLETED</option>
                <option value="SEVERE_INTERNAL_FAULT">SEVERE_INTERNAL_FAULT</option>
              </select>
            </label>
          </div>
          <button onClick={endTrip} type="button">
            End Trip
          </button>
        </section>

        <section className={`panel ${activeView === 'operations' ? 'wide' : ''}`}>
          <h2>Operations: Telemetry, Renewal, and Oversight</h2>
          <div className="form-grid">
            <label>
              Vehicle ID
              <input value={telemetryForm.vehicleId} onChange={(event) => setTelemetryForm({ ...telemetryForm, vehicleId: event.target.value })} />
            </label>
            <label>
              Battery
              <input value={telemetryForm.batteryLevel} onChange={(event) => setTelemetryForm({ ...telemetryForm, batteryLevel: event.target.value })} />
            </label>
            <label>
              Severity
              <select value={telemetryForm.severity} onChange={(event) => setTelemetryForm({ ...telemetryForm, severity: event.target.value })}>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </label>
            <label>
              Fault Code
              <input value={telemetryForm.faultCode} onChange={(event) => setTelemetryForm({ ...telemetryForm, faultCode: event.target.value })} />
            </label>
            <label className="toggle">
              <input
                checked={telemetryForm.tirePressureOk}
                onChange={(event) => setTelemetryForm({ ...telemetryForm, tirePressureOk: event.target.checked })}
                type="checkbox"
              />
              Tire pressure OK
            </label>
          </div>
          <div className="button-row">
            <button className="primary" onClick={sendTelemetry} type="button">
              Inject Fault Telemetry
            </button>
            <button onClick={simulateRenewal} type="button">
              Publish Renewal Event
            </button>
          </div>
          <label className="inline-field">
            Renewal User ID
            <input value={renewalUserId} onChange={(event) => setRenewalUserId(event.target.value)} />
          </label>
        </section>

        <section className={`panel ${activeView !== 'customer' ? 'wide' : ''}`}>
          <h2>System State</h2>
          <div className="stats">
            <div><strong>{vehicles.length}</strong><span>Vehicles</span></div>
            <div><strong>{bookings.length}</strong><span>Bookings</span></div>
            <div><strong>{trips.length}</strong><span>Trips</span></div>
            <div><strong>{tickets.length}</strong><span>Tickets</span></div>
            <div><strong>{payments.length}</strong><span>Payments</span></div>
            <div><strong>{notifications.length}</strong><span>Notifications</span></div>
          </div>
          <div className="data-grid">
            <div>
              <h3>Vehicles</h3>
              {vehicles.map((vehicle) => (
                <p key={vehicle.id}>{vehicle.id} / {vehicle.model} / {vehicle.status}</p>
              ))}
            </div>
            <div>
              <h3>Bookings</h3>
              {bookings.map((booking) => (
                <p key={booking.bookingId}>#{booking.bookingId} / vehicle {booking.vehicleId} / {booking.status} / {booking.reconciliationStatus}</p>
              ))}
            </div>
            <div>
              <h3>Trips</h3>
              {trips.map((trip) => (
                <p key={trip.tripId}>#{trip.tripId} / booking {trip.bookingId} / {trip.status} / {trip.durationHours.toFixed(2)}h</p>
              ))}
            </div>
            <div>
              <h3>Maintenance</h3>
              {tickets.map((ticket) => (
                <p key={ticket.ticketId}>Ticket {ticket.ticketId} / vehicle {ticket.vehicleId} / {ticket.damageSeverity}</p>
              ))}
            </div>
          </div>
        </section>

        <section className={`panel ${activeView === 'technician' ? 'wide' : ''}`}>
          <h2>Technician and Evidence Review</h2>
          <div className="data-grid">
            <div>
              <h3>Manual Review Queue</h3>
              {reviewQueue.length === 0 ? <p>No queued manual review cases.</p> : null}
              {reviewQueue.map((record) => (
                <p key={record.recordId}>Record {record.recordId} / vehicle {record.vehicleId} / {record.reviewState}</p>
              ))}
            </div>
            <div>
              <h3>All Records</h3>
              {records.map((record) => (
                <p key={record.recordId}>
                  {record.recordType} / vehicle {record.vehicleId} / {record.severity} / confidence {record.confidence.toFixed(2)}
                </p>
              ))}
            </div>
            <div>
              <h3>Payments</h3>
              {payments.map((payment) => (
                <p key={payment.paymentId}>Payment {payment.paymentId} / {payment.status} / SGD {payment.amount.toFixed(2)}</p>
              ))}
            </div>
            <div>
              <h3>Notifications</h3>
              {notifications.map((notification) => (
                <p key={notification.notificationId}>{notification.audience} / {notification.subject}</p>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
