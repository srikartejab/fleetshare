import { startTransition, useDeferredValue, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'

import { OpsPage } from './OpsPage'
import {
  customerStorageKey,
  fetchJson,
  localDateTime,
} from './appTypes'
import type { Booking, CustomerSummary, Notification, Payment, PricingSnapshot, RecordItem, SearchResponse, Trip, Vehicle, VehicleFilters } from './appTypes'
import {
  AccountPage,
  BookingDetailsPage,
  BookingProcessingPage,
  CustomerShell,
  DiscoverPage,
  HomePage,
  LandingPage,
  TripsPage,
} from './customerPages'

type PendingBooking = {
  status: 'processing' | 'success' | 'error'
  vehicleId: number
  bookingId?: number
  error?: string
}

function App() {
  const [customers, setCustomers] = useState<CustomerSummary[]>([])
  const [activeUserId, setActiveUserId] = useState(() => localStorage.getItem(customerStorageKey) ?? '')
  const [customerSummary, setCustomerSummary] = useState<CustomerSummary | null>(null)
  const [vehicles, setVehicles] = useState<Vehicle[]>([])
  const [vehicleFilters, setVehicleFilters] = useState<VehicleFilters>({ locations: [], vehicleTypes: [] })
  const [bookings, setBookings] = useState<Booking[]>([])
  const [trips, setTrips] = useState<Trip[]>([])
  const [payments, setPayments] = useState<Payment[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [records, setRecords] = useState<RecordItem[]>([])
  const [status, setStatus] = useState('Loading FleetShare customer experience.')
  const [busy, setBusy] = useState(false)
  const [searchResults, setSearchResults] = useState<Vehicle[]>([])
  const [searchSummary, setSearchSummary] = useState('')
  const [pendingBooking, setPendingBooking] = useState<PendingBooking | null>(null)
  const deferredSearchResults = useDeferredValue(searchResults)
  const [searchForm, setSearchForm] = useState({
    pickupLocation: '',
    vehicleType: '',
    startTime: localDateTime(1),
    endTime: localDateTime(4),
  })

  async function loadCustomers() {
    const allCustomers = await fetchJson<CustomerSummary[]>('/pricing/customers')
    startTransition(() => {
      setCustomers(allCustomers)
    })
  }

  async function loadVehicleMetadata() {
    const [allVehicles, filters] = await Promise.all([
      fetchJson<Vehicle[]>('/vehicles'),
      fetchJson<VehicleFilters>('/vehicles/filters'),
    ])
    startTransition(() => {
      setVehicles(allVehicles)
      setVehicleFilters(filters)
      setSearchForm((current) => ({
        ...current,
        pickupLocation: current.pickupLocation || filters.locations[0] || '',
        vehicleType: current.vehicleType || filters.vehicleTypes[0] || '',
      }))
    })
  }

  async function refreshCustomerData(userId = activeUserId) {
    if (!userId) {
      startTransition(() => {
        setCustomerSummary(null)
        setBookings([])
        setTrips([])
        setPayments([])
        setNotifications([])
        setRecords([])
        setSearchResults([])
        setSearchSummary('')
      })
      return
    }

    const query = encodeURIComponent(userId)
    const [summary, bookingData, tripData, paymentData, notificationData, recordData, allVehicles] = await Promise.all([
      fetchJson<CustomerSummary>(`/pricing/customers/${query}/summary`),
      fetchJson<Booking[]>(`/bookings?userId=${query}`),
      fetchJson<Trip[]>(`/trips?userId=${query}`),
      fetchJson<Payment[]>(`/payments?userId=${query}`),
      fetchJson<Notification[]>(`/notifications?userId=${query}`),
      fetchJson<RecordItem[]>('/records'),
      fetchJson<Vehicle[]>('/vehicles'),
    ])

    startTransition(() => {
      setCustomerSummary(summary)
      setBookings(bookingData)
      setTrips(tripData)
      setPayments(paymentData)
      setNotifications(notificationData)
      setRecords(recordData)
      setVehicles(allVehicles)
    })
  }

  useEffect(() => {
    let cancelled = false
    setBusy(true)
    Promise.all([loadCustomers(), loadVehicleMetadata()])
      .then(() => {
        if (!cancelled) {
          setStatus('Choose a customer profile to enter the app.')
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : 'Unable to load demo data.')
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

  useEffect(() => {
    let cancelled = false
    if (!activeUserId) {
      setCustomerSummary(null)
      return
    }
    setBusy(true)
    refreshCustomerData(activeUserId)
      .then(() => {
        if (!cancelled) {
          setStatus('Customer dashboard synced.')
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setStatus(error instanceof Error ? error.message : 'Unable to sync customer dashboard.')
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
  }, [activeUserId])

  function activateCustomer(userId: string) {
    localStorage.setItem(customerStorageKey, userId)
    setActiveUserId(userId)
    setSearchResults([])
    setSearchSummary('')
  }

  function clearActiveCustomer() {
    localStorage.removeItem(customerStorageKey)
    setActiveUserId('')
    setPendingBooking(null)
    setStatus('Choose a customer profile to enter the app.')
  }

  async function runCustomerAction(action: () => Promise<void>, successMessage: string) {
    setBusy(true)
    try {
      await action()
      await Promise.all([loadCustomers(), refreshCustomerData()])
      setStatus(successMessage)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unexpected error')
    } finally {
      setBusy(false)
    }
  }

  function startReservation(vehicleId: number) {
    setPendingBooking({ status: 'processing', vehicleId })
    setBusy(true)
    setStatus('Confirming your reservation...')
    void (async () => {
      let bookingId: number | null = null
      try {
        const response = await fetchJson<{ bookingId: number; pricing: PricingSnapshot }>(`/process-booking/reserve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            userId: activeUserId,
            vehicleId,
            pickupLocation: searchForm.pickupLocation,
            startTime: new Date(searchForm.startTime).toISOString(),
            endTime: new Date(searchForm.endTime).toISOString(),
            displayedPrice: 0,
            subscriptionPlanId: customerSummary?.planName ?? 'STANDARD_MONTHLY',
          }),
        })
        bookingId = response.bookingId
        setPendingBooking({ status: 'success', vehicleId, bookingId })
        setStatus(`Booking ${bookingId} confirmed.`)
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to confirm booking.'
        setPendingBooking({ status: 'error', vehicleId, error: message })
        setStatus(message)
        setBusy(false)
        return
      }

      try {
        await Promise.all([loadCustomers(), refreshCustomerData(activeUserId)])
      } catch {
        if (bookingId) {
          setStatus(`Booking ${bookingId} confirmed. Account data is still refreshing.`)
        }
      } finally {
        setBusy(false)
      }
    })()
  }

  const customerProfiles = customers.filter((customer) => customer.role === 'CUSTOMER')
  const selectedProfile = customerProfiles.find((customer) => customer.userId === activeUserId) ?? null
  const upcomingBookings = bookings
    .filter((booking) => booking.status !== 'CANCELLED' && booking.status !== 'RECONCILED' && !booking.tripId)
    .sort((left, right) => new Date(left.startTime).getTime() - new Date(right.startTime).getTime())
  const activeTrip = trips.find((trip) => trip.status === 'STARTED') ?? null
  const completedTrips = trips
    .filter((trip) => trip.status === 'ENDED')
    .sort((left, right) => new Date(right.endedAt ?? right.startedAt).getTime() - new Date(left.endedAt ?? left.startedAt).getTime())

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={<LandingPage busy={busy} customers={customerProfiles} onSelectCustomer={activateCustomer} status={status} />}
        />
        <Route path="/app" element={activeUserId ? <Navigate to="/app/home" replace /> : <Navigate to="/" replace />} />
        <Route
          path="/app/home"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <HomePage customerSummary={customerSummary} notifications={notifications} upcomingBookings={upcomingBookings} activeTrip={activeTrip} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/discover"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <DiscoverPage
                  customerSummary={customerSummary}
                  deferredSearchResults={deferredSearchResults}
                  searchForm={searchForm}
                  searchSummary={searchSummary}
                  vehicleFilters={vehicleFilters}
                  onReserve={startReservation}
                  onSearch={async () => {
                    const params = new URLSearchParams({
                      userId: activeUserId,
                      pickupLocation: searchForm.pickupLocation,
                      vehicleType: searchForm.vehicleType,
                      startTime: new Date(searchForm.startTime).toISOString(),
                      endTime: new Date(searchForm.endTime).toISOString(),
                      subscriptionPlanId: customerSummary?.planName ?? 'STANDARD_MONTHLY',
                    })
                    const result = await fetchJson<SearchResponse>(`/search-vehicles/search?${params.toString()}`)
                    startTransition(() => {
                      setSearchResults(result.vehicleList)
                      setSearchSummary(result.availabilitySummary)
                    })
                  }}
                  setSearchForm={setSearchForm}
                />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/bookings/processing"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <BookingProcessingPage pendingBooking={pendingBooking} vehicles={vehicles} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/bookings/:bookingId"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <BookingDetailsPage bookings={bookings} customerSummary={customerSummary} vehicles={vehicles} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <TripsPage
                  activeTrip={activeTrip}
                  bookings={bookings}
                  completedTrips={completedTrips}
                  onEndTrip={(bookingId, tripId, vehicleId, endReason) =>
                    runCustomerAction(async () => {
                      await fetchJson('/end-trip/request', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          bookingId,
                          tripId,
                          vehicleId,
                          userId: activeUserId,
                          endReason,
                        }),
                      })
                    }, 'Trip ended and pricing finalized.')
                  }
                  onStartTrip={(bookingId, vehicleId, notes) =>
                    runCustomerAction(async () => {
                      await fetchJson('/trips/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          bookingId,
                          vehicleId,
                          userId: activeUserId,
                          notes,
                        }),
                      })
                    }, 'Trip started successfully.')
                  }
                  onSubmitInspection={(bookingId, vehicleId, notes, photo) =>
                    runCustomerAction(async () => {
                      const formData = new FormData()
                      formData.append('bookingId', String(bookingId))
                      formData.append('vehicleId', String(vehicleId))
                      formData.append('userId', activeUserId)
                      formData.append('notes', notes)
                      if (photo) {
                        formData.append('photos', photo)
                      }
                      await fetchJson('/damage-assessment/external', {
                        method: 'POST',
                        body: formData,
                      })
                    }, 'Pre-trip inspection submitted.')
                  }
                  upcomingBookings={upcomingBookings}
                  vehicles={vehicles}
                  records={records}
                />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/account"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <AccountPage customerSummary={customerSummary} notifications={notifications} payments={payments} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/ops"
          element={<OpsPage activeUserId={activeUserId} onCustomerDataChanged={() => Promise.all([loadCustomers(), refreshCustomerData()]).then(() => undefined)} />}
        />
        <Route path="*" element={<Navigate to={activeUserId ? '/app/home' : '/'} replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
