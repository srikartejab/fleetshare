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
  ReservationDraft,
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
  BookingReviewPage,
  CustomerShell,
  EndTripCompletePage,
  EndTripConfirmPage,
  EndTripInspectionPage,
  EndTripInspectionProcessingPage,
  EndTripLockProcessingPage,
  EndTripReviewPage,
  HomePage,
  LandingPage,
  PreTripInspectionProcessingPage,
  PreTripInspectionResultPage,
  TripProblemPage,
  TripProblemProcessingPage,
  TripProblemResultPage,
  TripUnlockProcessingPage,
  TripsPage,
  WalletPage,
} from './customerMobilePages'

type PendingBooking = {
  status: 'processing' | 'success' | 'error'
  vehicleId: number
  bookingId?: number
  error?: string
}

type PendingInspectionRequest = {
  bookingId: number
  vehicleId: number
  notes: string
  photo: File | null
}

type PendingUnlockRequest = {
  bookingId: number
  vehicleId: number
  notes: string
}

type PendingProblemRequest = {
  tripId: number
  notes: string
}

type PendingPostTripInspectionRequest = {
  tripId: number
  notes: string
  photo: File | null
  endReason: string
}

type PendingEndTripRequest = {
  tripId: number
  endReason: string
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
  const [reservationDraft, setReservationDraft] = useState<ReservationDraft | null>(null)
  const [pendingBooking, setPendingBooking] = useState<PendingBooking | null>(null)
  const [pendingInspectionRequest, setPendingInspectionRequest] = useState<PendingInspectionRequest | null>(null)
  const [pendingUnlockRequest, setPendingUnlockRequest] = useState<PendingUnlockRequest | null>(null)
  const [pendingProblemRequest, setPendingProblemRequest] = useState<PendingProblemRequest | null>(null)
  const [pendingPostTripInspectionRequest, setPendingPostTripInspectionRequest] = useState<PendingPostTripInspectionRequest | null>(null)
  const [pendingEndTripRequest, setPendingEndTripRequest] = useState<PendingEndTripRequest | null>(null)
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
        setReservationDraft(null)
        setPendingInspectionRequest(null)
        setPendingUnlockRequest(null)
        setPendingProblemRequest(null)
        setPendingPostTripInspectionRequest(null)
        setPendingEndTripRequest(null)
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
    setReservationDraft(null)
    setPendingInspectionRequest(null)
    setPendingUnlockRequest(null)
    setPendingProblemRequest(null)
    setPendingPostTripInspectionRequest(null)
    setPendingEndTripRequest(null)
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
    setReservationDraft(null)
    setPendingInspectionRequest(null)
    setPendingUnlockRequest(null)
    setSearchResponse(null)
    setLatestInspectionResult(null)
    setReportedProblem(null)
    setPostTripInspectionResult(null)
    setEndTripResult(null)
    setStatus('Choose a customer profile to enter the app.')
  }

  async function refreshCustomerViews(userId = activeUserId) {
    await Promise.allSettled([loadCustomers(), refreshCustomerData(userId)])
  }

  async function runCustomerAction<T>(action: () => Promise<T>, successMessage: string | ((result: T) => string)) {
    setBusy(true)
    try {
      const result = await action()
      await refreshCustomerViews()
      setStatus(typeof successMessage === 'function' ? successMessage(result) : successMessage)
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unexpected error')
    } finally {
      setBusy(false)
    }
  }

  function beginReservationReview(vehicle: Vehicle) {
    setPendingBooking(null)
    const bookingHours = Math.max(
      (new Date(searchForm.endTime).getTime() - new Date(searchForm.startTime).getTime()) / (1000 * 60 * 60),
      0,
    )
    const pickupLocationLabel =
      vehicleFilters.locationOptions?.find((location) => location.id === searchForm.pickupLocation)?.label ??
      vehicle.stationName ??
      searchForm.pickupLocation
    setReservationDraft({
      vehicle,
      pickupLocationLabel,
      startTime: searchForm.startTime,
      endTime: searchForm.endTime,
      pricing: {
        estimatedPrice: vehicle.estimatedPrice ?? 0,
        allowanceStatus: vehicle.allowanceStatus ?? 'Pricing summary unavailable',
        crossCycleBooking: vehicle.crossCycleBooking ?? false,
        hourlyRate: vehicle.hourlyRate ?? customerSummary?.hourlyRate ?? 0,
        totalHours: vehicle.totalHours ?? bookingHours,
        currentCycleHours: vehicle.currentCycleHours ?? bookingHours,
        includedHoursRemainingBefore: vehicle.includedHoursRemainingBefore ?? customerSummary?.remainingHoursThisCycle ?? 0,
        includedHoursApplied: vehicle.includedHoursApplied ?? 0,
        includedHoursRemainingAfter: vehicle.includedHoursRemainingAfter ?? customerSummary?.remainingHoursThisCycle ?? 0,
        billableHours: vehicle.billableHours ?? 0,
        provisionalPostMidnightHours: vehicle.provisionalPostMidnightHours ?? 0,
        provisionalCharge: vehicle.provisionalCharge ?? 0,
        renewalDate: vehicle.renewalDate ?? customerSummary?.renewalDate,
        customerSummary: customerSummary ?? undefined,
      },
    })
    setStatus('Review the booking charges before confirming the reservation.')
  }

  function confirmReservation() {
    if (!reservationDraft) {
      setStatus('Choose a vehicle from Discover before confirming a booking.')
      return
    }

    const vehicleId = reservationDraft.vehicle.vehicleId ?? reservationDraft.vehicle.id
    setPendingBooking({ status: 'processing', vehicleId })
    setReservationDraft(null)
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
            pickupLocation: reservationDraft.pickupLocationLabel,
            startTime: new Date(reservationDraft.startTime).toISOString(),
            endTime: new Date(reservationDraft.endTime).toISOString(),
            displayedPrice: reservationDraft.pricing.estimatedPrice,
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
    setStatus('Assessing the reported issue...')
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
      await refreshCustomerViews(activeUserId)
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

  function queueTripProblem(notes: string) {
    if (!activeTrip) {
      throw new Error('No active trip found.')
    }
    setReportedProblem(null)
    setPendingProblemRequest({
      tripId: activeTrip.tripId,
      notes,
    })
  }

  async function submitQueuedPreTripInspection(request: PendingInspectionRequest) {
    setBusy(true)
    setStatus('AI is checking the inspection now...')
    try {
      const formData = new FormData()
      formData.append('bookingId', String(request.bookingId))
      formData.append('vehicleId', String(request.vehicleId))
      formData.append('userId', activeUserId)
      formData.append('notes', request.notes)
      if (request.photo) {
        formData.append('photos', request.photo)
      }
      const result = await fetchJson<InspectionSubmissionResult>('/damage-assessment/external', {
        method: 'POST',
        body: formData,
      })
      await refreshCustomerViews()
      setLatestInspectionResult(result)
      setStatus(
        result.tripStatus === 'CLEARED'
          ? result.warningMessage
          : `Inspection submitted. ${result.warningMessage}`,
      )
      return result
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unexpected error')
      throw error
    } finally {
      setBusy(false)
    }
  }

  async function startQueuedTripUnlock(request: PendingUnlockRequest) {
    setBusy(true)
    setStatus('Unlocking vehicle...')
    try {
      setReportedProblem(null)
      setPostTripInspectionResult(null)
      setEndTripResult(null)
      await fetchJson('/trips/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bookingId: request.bookingId,
          vehicleId: request.vehicleId,
          userId: activeUserId,
          notes: request.notes,
        }),
      })
      await refreshCustomerViews()
      setStatus('Trip started successfully.')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Unexpected error')
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
      await refreshCustomerViews(activeUserId)
      setPostTripInspectionResult(result)
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

  function queuePostTripInspection(notes: string, photo: File | null, endReason: string) {
    if (!activeTrip) {
      throw new Error('No active trip found.')
    }
    setPostTripInspectionResult(null)
    setEndTripResult(null)
    setPendingPostTripInspectionRequest({
      tripId: activeTrip.tripId,
      notes,
      photo,
      endReason,
    })
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
      await refreshCustomerViews(activeUserId)
      setEndTripResult(result)
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

  function queueEndTrip(endReason: string) {
    if (!activeTrip) {
      throw new Error('No active trip found.')
    }
    setEndTripResult(null)
    setPendingEndTripRequest({
      tripId: activeTrip.tripId,
      endReason,
    })
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
                onReserve={beginReservationReview}
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
          path="/app/bookings/review"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <BookingReviewPage
                  customerSummary={customerSummary ?? selectedProfile}
                  draft={reservationDraft}
                  onConfirmBooking={confirmReservation}
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
                  onQueueInspection={(request) => {
                    setPendingInspectionRequest(request)
                    setLatestInspectionResult(null)
                  }}
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
          path="/app/trips/inspection-processing"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <PreTripInspectionProcessingPage
                  latestInspectionResult={latestInspectionResult}
                  records={records}
                  request={pendingInspectionRequest}
                  vehicles={vehicles}
                  onSubmitInspection={submitQueuedPreTripInspection}
                />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/inspection-result"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <PreTripInspectionResultPage
                  latestInspectionResult={latestInspectionResult}
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
                  onQueueUnlock={(request) => setPendingUnlockRequest(request)}
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
          path="/app/trips/unlock-processing"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <TripUnlockProcessingPage
                  activeTrip={activeTrip}
                  request={pendingUnlockRequest}
                  vehicles={vehicles}
                  onUnlock={startQueuedTripUnlock}
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
                <TripProblemPage activeTrip={activeTrip} onQueueProblem={queueTripProblem} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/problem-processing"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <TripProblemProcessingPage
                  activeTrip={activeTrip}
                  onSubmitProblem={submitTripProblem}
                  reportedProblem={reportedProblem}
                  request={pendingProblemRequest}
                />
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
                <EndTripInspectionPage activeTrip={activeTrip} onQueueInspection={queuePostTripInspection} vehicles={vehicles} />
              </CustomerShell>
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/app/trips/end-inspection-processing"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <EndTripInspectionProcessingPage
                  activeTrip={activeTrip}
                  onSubmitInspection={submitPostTripInspection}
                  postTripInspectionResult={postTripInspectionResult}
                  request={pendingPostTripInspectionRequest}
                  vehicles={vehicles}
                />
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
                  onQueueEndTrip={queueEndTrip}
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
          path="/app/trips/end-lock-processing"
          element={
            activeUserId ? (
              <CustomerShell activeUser={selectedProfile} busy={busy} status={status} onSwitchUser={clearActiveCustomer}>
                <EndTripLockProcessingPage
                  activeTrip={activeTrip}
                  endTripResult={endTripResult}
                  onConfirmEndTrip={completeEndTrip}
                  request={pendingEndTripRequest}
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
          element={<OpsPage activeUserId={activeUserId} onCustomerDataChanged={() => refreshCustomerViews().then(() => undefined)} />}
        />
        <Route path="*" element={<Navigate to={activeUserId ? '/app/home' : '/'} replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
