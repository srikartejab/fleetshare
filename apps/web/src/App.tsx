import { startTransition, useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import './App.css'

import { OpsPage } from './OpsPage'
import { SearchExperiencePage } from './SearchExperiencePage'
import {
  customerStorageKey,
  fetchJson,
  localDateTime,
} from './appTypes'
import type {
  Booking,
  CustomerSummary,
  EndTripResult,
  InternalDamageResult,
  InspectionCancellationResult,
  InspectionSubmissionResult,
  Notification,
  Payment,
  PostTripInspectionResult,
  PricingSnapshot,
  RecordItem,
  SearchResponse,
  Trip,
  Vehicle,
  VehicleFilters,
  WalletLedgerEntry,
} from './appTypes'
import {
  AccountPage,
  BookingDetailsPage,
  BookingProcessingPage,
  CustomerShell,
  EndTripCompletePage,
  EndTripConfirmPage,
  EndTripInspectionPage,
  EndTripReviewPage,
  HomePage,
  LandingPage,
  TripProblemPage,
  TripProblemResultPage,
  TripsPage,
  WalletPage,
} from './customerMobilePages'

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
  const [walletLedger, setWalletLedger] = useState<WalletLedgerEntry[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [records, setRecords] = useState<RecordItem[]>([])
  const [status, setStatus] = useState('Loading FleetShare customer experience.')
  const [busy, setBusy] = useState(false)
  const [searchResponse, setSearchResponse] = useState<SearchResponse | null>(null)
  const [pendingBooking, setPendingBooking] = useState<PendingBooking | null>(null)
  const [latestInspectionResult, setLatestInspectionResult] = useState<InspectionSubmissionResult | null>(null)
  const [reportedProblem, setReportedProblem] = useState<InternalDamageResult | null>(null)
  const [postTripInspectionResult, setPostTripInspectionResult] = useState<PostTripInspectionResult | null>(null)
  const [endTripResult, setEndTripResult] = useState<EndTripResult | null>(null)
  const [searchForm, setSearchForm] = useState({
    pickupLocation: '',
    vehicleType: '',
    startTime: localDateTime(1),
    endTime: localDateTime(4),
  })

  async function fetchOrDefault<T>(path: string, fallback: T) {
    try {
      return await fetchJson<T>(path)
    } catch {
      return fallback
    }
  }

  async function loadCustomers() {
    const allCustomers = await fetchJson<CustomerSummary[]>('/pricing/customers')
    startTransition(() => {
      setCustomers(allCustomers)
    })
  }

  async function loadVehicleMetadata() {
    const allVehicles = await fetchJson<Vehicle[]>('/vehicles')
    const filters = await fetchJson<VehicleFilters>('/vehicles/filters').catch(() => {
      const locations = Array.from(new Set(allVehicles.map((vehicle) => vehicle.stationId ?? vehicle.zone)))
      const locationOptions = locations.map((locationId) => {
        const sampleVehicle = allVehicles.find((vehicle) => (vehicle.stationId ?? vehicle.zone) === locationId)
        return {
          id: locationId,
          label: sampleVehicle?.stationName ?? locationId,
          address: sampleVehicle?.stationAddress ?? sampleVehicle?.zone ?? locationId,
          area: sampleVehicle?.area ?? sampleVehicle?.zone ?? 'Singapore',
          latitude: sampleVehicle?.latitude ?? 1.3521,
          longitude: sampleVehicle?.longitude ?? 103.8198,
        }
      })
      return {
        locations,
        vehicleTypes: Array.from(new Set(allVehicles.map((vehicle) => vehicle.vehicleType))).sort(),
        locationOptions,
      }
    })
    startTransition(() => {
      setVehicles(allVehicles)
      setVehicleFilters(filters)
      setSearchForm((current) => ({
        ...current,
        pickupLocation: current.pickupLocation || filters.locationOptions?.[0]?.id || filters.locations[0] || '',
        vehicleType: current.vehicleType,
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
        setWalletLedger([])
        setNotifications([])
        setRecords([])
        setSearchResponse(null)
      })
      return
    }

    const query = encodeURIComponent(userId)
    const fallbackSummary = customers.find((customer) => customer.userId === userId) ?? null
    const [summary, bookingData, tripData, paymentData, ledgerData, notificationData, recordData, allVehicles] = await Promise.all([
      fetchOrDefault<CustomerSummary | null>(`/pricing/customers/${query}/summary`, fallbackSummary),
      fetchOrDefault<Booking[]>(`/bookings?userId=${query}`, []),
      fetchOrDefault<Trip[]>(`/trips?userId=${query}`, []),
      fetchOrDefault<Payment[]>(`/payments?userId=${query}`, []),
      fetchOrDefault<WalletLedgerEntry[]>(`/pricing/customers/${query}/ledger`, []),
      fetchOrDefault<Notification[]>(`/notifications?userId=${query}`, []),
      fetchOrDefault<RecordItem[]>('/records', []),
      fetchOrDefault<Vehicle[]>('/vehicles', vehicles),
    ])

    startTransition(() => {
      setCustomerSummary(summary)
      setBookings(bookingData)
      setTrips(tripData)
      setPayments(paymentData)
      setWalletLedger(ledgerData)
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
    setCustomerSummary(null)
    setBookings([])
    setTrips([])
    setPayments([])
    setWalletLedger([])
    setNotifications([])
    setRecords([])
    setSearchResponse(null)
    setLatestInspectionResult(null)
    setReportedProblem(null)
    setPostTripInspectionResult(null)
    setEndTripResult(null)
  }

  function clearActiveCustomer() {
    localStorage.removeItem(customerStorageKey)
    setActiveUserId('')
    setPendingBooking(null)
    setSearchResponse(null)
    setLatestInspectionResult(null)
    setReportedProblem(null)
    setPostTripInspectionResult(null)
    setEndTripResult(null)
    setStatus('Choose a customer profile to enter the app.')
  }

  async function runCustomerAction<T>(action: () => Promise<T>, successMessage: string | ((result: T) => string)) {
    setBusy(true)
    try {
      const result = await action()
      await Promise.all([loadCustomers(), refreshCustomerData()])
      setStatus(typeof successMessage === 'function' ? successMessage(result) : successMessage)
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
        const reserve = await fetchJson<{ bookingId: number; pricing: PricingSnapshot }>(`/process-booking/reserve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            userId: activeUserId,
            vehicleId,
            pickupLocation:
              vehicleFilters.locationOptions?.find((location) => location.id === searchForm.pickupLocation)?.label ??
              searchForm.pickupLocation,
            startTime: new Date(searchForm.startTime).toISOString(),
            endTime: new Date(searchForm.endTime).toISOString(),
            displayedPrice: 0,
            subscriptionPlanId: customerSummary?.planName ?? 'STANDARD_MONTHLY',
          }),
        })
        bookingId = reserve.bookingId
        await fetchJson<{ bookingId: number; paymentId: number; status: string }>(`/process-booking/pay`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bookingId: reserve.bookingId,
            userId: activeUserId,
          }),
        })
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

  async function submitTripProblem(notes: string) {
    if (!activeTrip) {
      throw new Error('No active trip found.')
    }
    setBusy(true)
    try {
      const result = await fetchJson<InternalDamageResult>('/internal-damage/fault-alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bookingId: activeTrip.bookingId,
          tripId: activeTrip.tripId,
          vehicleId: activeTrip.vehicleId,
          userId: activeUserId,
          sensorType: 'USER_REPORT',
          notes,
        }),
      })
      setReportedProblem(result)
      await Promise.all([refreshCustomerData(activeUserId), loadCustomers()])
      setStatus(result.recommendedAction)
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to submit the vehicle problem.'
      setStatus(message)
      throw error
    } finally {
      setBusy(false)
    }
  }

  async function submitPostTripInspection(notes: string, photo: File | null) {
    if (!activeTrip) {
      throw new Error('No active trip found.')
    }
    setBusy(true)
    try {
      const formData = new FormData()
      formData.append('bookingId', String(activeTrip.bookingId))
      formData.append('tripId', String(activeTrip.tripId))
      formData.append('vehicleId', String(activeTrip.vehicleId))
      formData.append('userId', activeUserId)
      formData.append('notes', notes)
      if (photo) {
        formData.append('photos', photo)
      }
      const result = await fetchJson<PostTripInspectionResult>('/damage-assessment/post-trip', {
        method: 'POST',
        body: formData,
      })
      setPostTripInspectionResult(result)
      await Promise.all([refreshCustomerData(activeUserId), loadCustomers()])
      setStatus(result.warningMessage)
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to save the post-trip inspection.'
      setStatus(message)
      throw error
    } finally {
      setBusy(false)
    }
  }

  async function completeEndTrip(endReason: string) {
    if (!activeTrip) {
      throw new Error('No active trip found.')
    }
    setBusy(true)
    try {
      const result = await fetchJson<EndTripResult>('/end-trip/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bookingId: activeTrip.bookingId,
          tripId: activeTrip.tripId,
          vehicleId: activeTrip.vehicleId,
          userId: activeUserId,
          endReason,
        }),
      })
      setEndTripResult(result)
      await Promise.all([refreshCustomerData(activeUserId), loadCustomers()])
      setStatus('Trip ended and pricing finalized.')
      return result
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to end the trip.'
      setStatus(message)
      throw error
    } finally {
      setBusy(false)
    }
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
  const historicalBookings = bookings
    .filter((booking) => booking.bookingId !== activeTrip?.bookingId)
    .filter((booking) => booking.status === 'CANCELLED' || booking.status === 'COMPLETED' || booking.status === 'RECONCILED' || Boolean(booking.tripId))
    .sort((left, right) => new Date(right.endTime ?? right.startTime).getTime() - new Date(left.endTime ?? left.startTime).getTime())

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
                <HomePage customerSummary={customerSummary ?? selectedProfile} notifications={notifications} upcomingBookings={upcomingBookings} activeTrip={activeTrip} />
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
              <SearchExperiencePage
                activeUser={selectedProfile}
                busy={busy}
                customerSummary={customerSummary ?? selectedProfile}
                onReserve={startReservation}
                onSearch={async () => {
                  const params = new URLSearchParams({
                    userId: activeUserId,
                    pickupLocation: searchForm.pickupLocation,
                    startTime: new Date(searchForm.startTime).toISOString(),
                    endTime: new Date(searchForm.endTime).toISOString(),
                    subscriptionPlanId: customerSummary?.planName ?? 'STANDARD_MONTHLY',
                  })
                  if (searchForm.vehicleType) {
                    params.set('vehicleType', searchForm.vehicleType)
                  }
                  const result = await fetchJson<SearchResponse>(`/process-booking/search?${params.toString()}`)
                  startTransition(() => {
                    setSearchResponse(result)
                  })
                }}
                onSwitchUser={clearActiveCustomer}
                searchForm={searchForm}
                searchResponse={searchResponse}
                setSearchForm={setSearchForm}
                status={status}
                vehicleFilters={vehicleFilters}
              />
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
                <BookingDetailsPage bookings={bookings} customerSummary={customerSummary ?? selectedProfile} vehicles={vehicles} />
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
                  completedTrips={completedTrips}
                  historicalBookings={historicalBookings}
                  onCancelModerateDamage={(bookingId, vehicleId) =>
                    runCustomerAction(async () => {
                      const result = await fetchJson<InspectionCancellationResult>('/damage-assessment/external/customer-cancel', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                          bookingId,
                          vehicleId,
                          userId: activeUserId,
                        }),
                      })
                      return result
                    }, (result) => result.message)
                  }
                  onStartTrip={(bookingId, vehicleId, notes) =>
                    runCustomerAction(async () => {
                      setReportedProblem(null)
                      setPostTripInspectionResult(null)
                      setEndTripResult(null)
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
                      const result = await fetchJson<InspectionSubmissionResult>('/damage-assessment/external', {
                        method: 'POST',
                        body: formData,
                      })
                      setLatestInspectionResult(result)
                      return result
                    }, (result) =>
                      result.tripStatus === 'CLEARED'
                        ? result.warningMessage
                        : `Inspection submitted. ${result.warningMessage}`
                    )
                  }
                  upcomingBookings={upcomingBookings}
                  vehicles={vehicles}
                  records={records}
                  latestInspectionResult={latestInspectionResult}
                />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/report-problem"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <TripProblemPage activeTrip={activeTrip} onSubmitProblem={submitTripProblem} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/problem-advisory"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <TripProblemResultPage activeTrip={activeTrip} reportedProblem={reportedProblem} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/end-inspection"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <EndTripInspectionPage activeTrip={activeTrip} onSubmitInspection={submitPostTripInspection} vehicles={vehicles} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/end-review"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <EndTripReviewPage activeTrip={activeTrip} postTripInspectionResult={postTripInspectionResult} vehicles={vehicles} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/end-confirm"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <EndTripConfirmPage
                  activeTrip={activeTrip}
                  onConfirmEndTrip={completeEndTrip}
                  postTripInspectionResult={postTripInspectionResult}
                  vehicles={vehicles}
                />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/end-complete"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <EndTripCompletePage endTripResult={endTripResult} postTripInspectionResult={postTripInspectionResult} />
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
                <AccountPage customerSummary={customerSummary ?? selectedProfile} notifications={notifications} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/wallet"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <WalletPage
                  bookings={bookings}
                  customerSummary={customerSummary ?? selectedProfile}
                  ledgerEntries={walletLedger}
                  payments={payments}
                />
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
