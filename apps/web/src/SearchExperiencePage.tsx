import { type Dispatch, type SetStateAction, useEffect, useEffectEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MapContainer, Marker, TileLayer, useMap } from 'react-leaflet'
import { divIcon, type DivIcon } from 'leaflet'
import 'leaflet/dist/leaflet.css'
import './searchExperience.css'

import {
  formatMoney,
  formatShortDate,
  type CustomerSummary,
  type SearchResponse,
  type Vehicle,
  type VehicleFilters,
} from './appTypes'

type SearchFormState = {
  pickupLocation: string
  vehicleType: string
  startTime: string
  endTime: string
}

function markerIcon(count: number, selected: boolean): DivIcon {
  const tone = selected ? 'search-marker--selected' : count > 0 ? 'search-marker--available' : 'search-marker--empty'
  return divIcon({
    className: 'search-marker-icon',
    html: `<div class="search-marker-hitbox"><div class="search-marker ${tone}"><span>${count}</span></div></div>`,
    iconSize: [60, 68],
    iconAnchor: [30, 58],
  })
}

function MapViewportController({
  center,
  zoom,
}: {
  center: { latitude: number; longitude: number }
  zoom: number
}) {
  const map = useMap()

  useEffect(() => {
    map.setView([center.latitude, center.longitude], zoom, { animate: false })
  }, [center.latitude, center.longitude, map, zoom])

  return null
}

function deviceTime() {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date())
}

function formatSearchSlotTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

function vehicleDisplayType(vehicle: Vehicle) {
  const byType: Record<string, string> = {
    SEDAN: 'Standard EV Sedan',
    COMPACT: 'Compact EV',
    SUV: 'Standard EV SUV',
    MPV: 'Family EV MPV',
    LUXURY: 'Premium EV',
  }
  return byType[vehicle.vehicleType] ?? 'Electric Vehicle'
}

function vehicleBadge(vehicle: Vehicle) {
  if (vehicle.vehicleType === 'SEDAN' || vehicle.vehicleType === 'COMPACT') {
    return 'New Driver'
  }
  if (vehicle.vehicleType === 'LUXURY') {
    return 'Premium'
  }
  return 'Popular'
}

function CarIllustration() {
  return (
    <svg aria-hidden="true" className="station-card__car" viewBox="0 0 220 118">
      <defs>
        <linearGradient id="car-body" x1="0%" x2="100%">
          <stop offset="0%" stopColor="#f9fbff" />
          <stop offset="100%" stopColor="#dbe6f5" />
        </linearGradient>
        <linearGradient id="car-shadow" x1="0%" x2="100%">
          <stop offset="0%" stopColor="rgba(25, 40, 64, 0.22)" />
          <stop offset="100%" stopColor="rgba(25, 40, 64, 0.06)" />
        </linearGradient>
      </defs>
      <ellipse cx="106" cy="96" rx="78" ry="12" fill="rgba(17, 35, 61, 0.12)" />
      <path d="M36 73c6-23 19-35 38-38l40-7c16-3 31 1 45 11l17 13c6 4 10 11 10 19v10H28l8-8Z" fill="url(#car-body)" />
      <path d="M80 34h45c10 0 20 3 28 9l13 9H65l15-18Z" fill="#eaf1fb" />
      <path d="M98 37h24l24 15H87l11-15Z" fill="#93a8c5" opacity="0.72" />
      <circle cx="66" cy="84" r="17" fill="#15243d" />
      <circle cx="66" cy="84" r="8" fill="#dfe6f1" />
      <circle cx="155" cy="84" r="17" fill="#15243d" />
      <circle cx="155" cy="84" r="8" fill="#dfe6f1" />
      <path d="M168 56h17c8 0 12 5 12 11v8h-18c-3-8-7-14-11-19Z" fill="#f3f7fd" />
      <path d="M38 77h20l-6 10H30l8-10Z" fill="#d7e0ec" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg aria-hidden="true" className="find-button__icon" viewBox="0 0 24 24">
      <circle cx="10.5" cy="10.5" r="5.8" fill="none" stroke="currentColor" strokeWidth="2.2" />
      <path d="m15 15 5.3 5.3" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="2.4" />
    </svg>
  )
}

function CalendarIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="4" y="6.2" width="16" height="13.2" rx="2.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M7.4 4v4M16.6 4v4M4 10.2h16" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
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

function FilterIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 6h16l-6.2 6.8v4.8l-3.6 1.7v-6.5L4 6Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
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

function CarouselArrowIcon({
  direction,
}: {
  direction: 'previous' | 'next'
}) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path
        d={direction === 'previous' ? 'm14.5 5.5-6 6 6 6' : 'm9.5 5.5 6 6-6 6'}
        fill="none"
        stroke="#1e5f96"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.7"
      />
    </svg>
  )
}

function MetaIcon({
  kind,
}: {
  kind: 'distance' | 'electric' | 'driver'
}) {
  if (kind === 'distance') {
    return <PinIcon />
  }
  if (kind === 'electric') {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24">
        <path d="M10.2 3.8 6.4 12h4.4l-1 8.2 7-10h-4.1l2.7-6.4Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.9" />
      </svg>
    )
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <circle cx="12" cy="8" r="3.2" fill="none" stroke="currentColor" strokeWidth="1.9" />
      <path d="M5.4 19.2a6.6 6.6 0 0 1 13.2 0" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.9" />
    </svg>
  )
}

function BottomNavIcon({
  kind,
}: {
  kind: 'account' | 'wallet' | 'bookings' | 'more' | 'finder' | 'locate' | 'list'
}) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
  switch (kind) {
    case 'wallet':
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <rect x="3.5" y="6.2" width="17" height="11.6" rx="2.2" {...common} />
          <path d="M15.2 11.9h5.3" {...common} />
        </svg>
      )
    case 'bookings':
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="8.2" {...common} />
          <path d="m8.6 12.2 2.2 2.2 4.5-4.7" {...common} />
        </svg>
      )
    case 'more':
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="M4.5 8.2 12 4l7.5 4.2v9.1L12 20l-7.5-2.7V8.2Z" {...common} />
          <path d="M4.5 8.2 12 12l7.5-3.8" {...common} />
        </svg>
      )
    case 'finder':
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="M7 15.6h10l-1.4-4.6H8.4L7 15.6Z" {...common} />
          <path d="m9 11 1.8-3.8h2.4L15 11" {...common} />
          <circle cx="8.8" cy="17.2" r="1.2" {...common} />
          <circle cx="15.2" cy="17.2" r="1.2" {...common} />
          <path d="M12 4.5v2.2M9.8 5.6 8 4.2M14.2 5.6 16 4.2" {...common} />
        </svg>
      )
    case 'locate':
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="4.5" {...common} />
          <path d="M12 3.8v3M12 17.2v3M3.8 12h3M17.2 12h3" {...common} />
        </svg>
      )
    case 'list':
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <path d="M7.4 7.3h10.4M7.4 12h10.4M7.4 16.7h10.4M4.8 7.3h.01M4.8 12h.01M4.8 16.7h.01" {...common} />
        </svg>
      )
    case 'account':
    default:
      return (
        <svg aria-hidden="true" viewBox="0 0 24 24">
          <circle cx="12" cy="8" r="3.2" {...common} />
          <path d="M5.3 19.2a6.7 6.7 0 0 1 13.4 0" {...common} />
        </svg>
      )
  }
}

export function SearchExperiencePage({
  activeUser,
  bookingWindowError,
  busy,
  customerSummary,
  onReserve,
  onSearch,
  onSwitchUser,
  searchForm,
  searchResponse,
  setSearchForm,
  status,
  vehicleFilters,
}: {
  activeUser: CustomerSummary | null
  bookingWindowError: string | null
  busy: boolean
  customerSummary: CustomerSummary | null
  onReserve: (vehicle: Vehicle) => void
  onSearch: () => Promise<void>
  onSwitchUser: () => void
  searchForm: SearchFormState
  searchResponse: SearchResponse | null
  setSearchForm: Dispatch<SetStateAction<SearchFormState>>
  status: string
  vehicleFilters: VehicleFilters
}) {
  const navigate = useNavigate()
  const [selectedStationId, setSelectedStationId] = useState(searchResponse?.selectedStationId ?? searchForm.pickupLocation)
  const [selectedVehicleIndex, setSelectedVehicleIndex] = useState(0)
  const [filterOpen, setFilterOpen] = useState(false)
  const [clock, setClock] = useState(() => deviceTime())
  const isBookingWindowInvalid = Boolean(bookingWindowError)
  const initialSearch = useEffectEvent(() => {
    if (!searchResponse && searchForm.pickupLocation && !isBookingWindowInvalid) {
      void onSearch()
    }
  })

  useEffect(() => {
    const timer = window.setInterval(() => setClock(deviceTime()), 1_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    initialSearch()
  }, [initialSearch, searchForm.pickupLocation, searchResponse])

  useEffect(() => {
    if (!searchResponse) {
      return
    }
    setSelectedStationId(searchResponse.selectedStationId ?? searchForm.pickupLocation)
  }, [searchForm.pickupLocation, searchResponse])

  useEffect(() => {
    setSelectedVehicleIndex(0)
  }, [selectedStationId, searchResponse])

  const selectedStation =
    searchResponse?.stationList.find((station) => station.stationId === selectedStationId) ??
    searchResponse?.stationList[0] ??
    null
  const stationVehicles = selectedStation?.vehicleList?.length
    ? selectedStation.vehicleList
    : selectedStation?.featuredVehicle
      ? [selectedStation.featuredVehicle]
      : []
  const activeVehicle = stationVehicles[selectedVehicleIndex] ?? stationVehicles[0] ?? null
  const hasVehicleCarousel = stationVehicles.length > 1
  const selectedLocationId = selectedStation?.stationId ?? searchForm.pickupLocation
  const selectedLocation =
    vehicleFilters.locationOptions?.find((location) => location.id === selectedLocationId) ?? vehicleFilters.locationOptions?.[0] ?? null
  const availabilitySummary = bookingWindowError ?? searchResponse?.availabilitySummary ?? (busy ? 'Finding nearby vehicles...' : 'Tap Find to load nearby vehicles')

  function selectStation(stationId: string) {
    if (stationId === selectedStationId) {
      return
    }
    setSelectedStationId(stationId)
  }

  return (
    <div className="search-experience">
      <header className="search-header">
        <div className="search-statusbar">
          <strong>{clock}</strong>
        </div>
        {selectedStation ? (
          <div className="search-header__titlebar">
            <button
              className="header-back-button"
              onClick={() => selectStation(searchResponse?.selectedStationId ?? searchForm.pickupLocation)}
              type="button"
            >
              <HeaderBackIcon />
            </button>
            <h1>{selectedStation.stationName}</h1>
            <button className="header-switch-link" onClick={onSwitchUser} type="button">
              {activeUser?.displayName?.split(' ')[0] ?? 'User'}
            </button>
          </div>
        ) : null}
      </header>

      <section className="search-panel">
        <div className="search-bar">
          <button className="search-slot" onClick={() => setFilterOpen(true)} type="button">
            <CalendarIcon />
            <div>
              <span>Pick Up</span>
              <strong>{formatSearchSlotTime(searchForm.startTime)}</strong>
              <small>{formatShortDate(searchForm.startTime)}</small>
            </div>
          </button>
          <button className="search-slot" onClick={() => setFilterOpen(true)} type="button">
            <CalendarIcon />
            <div>
              <span>Return</span>
              <strong>{formatSearchSlotTime(searchForm.endTime)}</strong>
              <small>{formatShortDate(searchForm.endTime)}</small>
            </div>
          </button>
          <button className="find-button" disabled={busy || isBookingWindowInvalid} onClick={() => void onSearch()} type="button">
            <SearchIcon />
            <span>{busy ? '...' : 'Find'}</span>
          </button>
        </div>

        <div className="location-bar">
          <div className="location-bar__label">
            <PinIcon />
            <strong>{selectedLocation?.label ?? 'Select location'}</strong>
          </div>
          <button className="filter-trigger" onClick={() => setFilterOpen(true)} type="button">
            <FilterIcon />
            <span>Filter</span>
          </button>
        </div>
      </section>

      <main className={`search-map-shell ${selectedStation ? 'search-map-shell--with-card' : ''}`}>
        <div className={`availability-pill ${searchResponse ? '' : 'availability-pill--loading'}`}>{availabilitySummary}</div>
        <MapContainer
          attributionControl={false}
          center={[
            searchResponse?.mapCenter?.latitude ?? selectedLocation?.latitude ?? 1.3725,
            searchResponse?.mapCenter?.longitude ?? selectedLocation?.longitude ?? 103.9622,
          ]}
          className="search-map"
          zoom={13.6}
          zoomControl={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MapViewportController
            center={{
              latitude: selectedStation?.latitude ?? searchResponse?.mapCenter?.latitude ?? selectedLocation?.latitude ?? 1.3725,
              longitude: selectedStation?.longitude ?? searchResponse?.mapCenter?.longitude ?? selectedLocation?.longitude ?? 103.9622,
            }}
            zoom={selectedStation ? 15.1 : 13.6}
          />
          {(searchResponse?.stationList ?? []).map((station) => (
            <Marker
              eventHandlers={{
                click: () => selectStation(station.stationId),
              }}
              icon={markerIcon(station.availableVehicleCount, station.stationId === selectedStationId)}
              key={station.stationId}
              position={[station.latitude, station.longitude]}
            />
          ))}
        </MapContainer>

        <div className="map-utility-bar">
          <button type="button">
            <BottomNavIcon kind="locate" />
          </button>
          <button type="button">
            <BottomNavIcon kind="list" />
          </button>
        </div>

        {selectedStation && !isBookingWindowInvalid ? (
          <section className="station-card">
            {activeVehicle ? (
              <>
                {hasVehicleCarousel ? (
                  <div className="station-card__carousel">
                    <div>
                      <span className="station-card__subheading">Available at this station</span>
                      <strong>
                        {selectedVehicleIndex + 1} of {stationVehicles.length}
                      </strong>
                    </div>
                    <div className="station-card__carousel-controls">
                      <button
                        aria-label="Show previous vehicle"
                        className="station-card__carousel-button"
                        onClick={() => setSelectedVehicleIndex((current) => (current - 1 + stationVehicles.length) % stationVehicles.length)}
                        type="button"
                      >
                        <CarouselArrowIcon direction="previous" />
                      </button>
                      <button
                        aria-label="Show next vehicle"
                        className="station-card__carousel-button"
                        onClick={() => setSelectedVehicleIndex((current) => (current + 1) % stationVehicles.length)}
                        type="button"
                      >
                        <CarouselArrowIcon direction="next" />
                      </button>
                    </div>
                  </div>
                ) : null}
                <div className="station-card__hero">
                  <div className="station-card__hero-copy">
                    <h2>{vehicleDisplayType(activeVehicle)}</h2>
                    <p>{activeVehicle.model} or similar</p>
                  </div>
                  <div className="station-card__hero-cta">
                    <CarIllustration />
                  </div>
                </div>
                <div className="station-card__meta">
                  <span>
                    <MetaIcon kind="distance" />
                    {activeVehicle.distanceKm?.toFixed(2) ?? selectedStation.distanceKm.toFixed(2)} km
                  </span>
                  <span>
                    <MetaIcon kind="electric" />
                    Electric
                  </span>
                  <span>
                    <MetaIcon kind="driver" />
                    {vehicleBadge(activeVehicle)}
                  </span>
                </div>
                <div className="station-card__action-row">
                  <button
                    className="reserve-button"
                    onClick={() => {
                      onReserve(activeVehicle)
                      navigate('/app/bookings/review')
                    }}
                    type="button"
                  >
                    <strong>{formatMoney(activeVehicle.estimatedPrice ?? 0)}</strong>
                    <span>Reserve</span>
                  </button>
                </div>
                <div className="station-card__divider" />
              </>
            ) : (
              <>
                <div className="station-card__hero station-card__hero--empty">
                  <div>
                    <h2>{selectedStation.stationName}</h2>
                    <p>No cars free right now at this station.</p>
                  </div>
                  <CarIllustration />
                </div>
                <div className="station-card__divider" />
                <div className="station-card__footer station-card__footer--empty">
                  <div>
                    <span className="station-card__subheading">Next available timing</span>
                    <strong>{selectedStation.nextAvailableTiming ?? 'Check again later'}</strong>
                  </div>
                  <button className="reserve-button reserve-button--disabled" disabled type="button">
                    <strong>0</strong>
                    <span>Unavailable</span>
                  </button>
                </div>
              </>
            )}
          </section>
        ) : null}
      </main>

      <nav className="search-bottomnav">
        <Link to="/app/account">
          <BottomNavIcon kind="account" />
          <span>Account</span>
        </Link>
        <Link to="/app/wallet">
          <BottomNavIcon kind="wallet" />
          <span>e-Wallet</span>
        </Link>
        <Link className="bottomnav-center" to="/app/discover">
          <BottomNavIcon kind="finder" />
        </Link>
        <Link to="/app/trips">
          <BottomNavIcon kind="bookings" />
          <span>Bookings</span>
        </Link>
        <Link to="/app/home">
          <BottomNavIcon kind="more" />
          <span>More</span>
        </Link>
      </nav>

      <section className={`filter-sheet ${filterOpen ? 'filter-sheet--open' : ''}`} aria-hidden={!filterOpen}>
        <div className="filter-sheet__scrim" onClick={() => setFilterOpen(false)} />
        <div className="filter-sheet__panel">
          <div className="filter-sheet__handle" />
          <div className="filter-sheet__header">
            <div>
              <p className="mini-label">Search filters</p>
              <h2>Tune the vehicle search</h2>
            </div>
            <span>{bookingWindowError ?? status}</span>
          </div>
          <label>
            Pick-up location
            <select
              value={searchForm.pickupLocation}
              onChange={(event) => selectStation(event.target.value)}
            >
              {(vehicleFilters.locationOptions ?? []).map((location) => (
                <option key={location.id} value={location.id}>
                  {location.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Vehicle type
            <select
              value={searchForm.vehicleType}
              onChange={(event) => setSearchForm((current) => ({ ...current, vehicleType: event.target.value }))}
            >
              <option value="">All vehicles</option>
              {vehicleFilters.vehicleTypes.map((vehicleType) => (
                <option key={vehicleType} value={vehicleType}>
                  {vehicleType}
                </option>
              ))}
            </select>
          </label>
          <div className="filter-sheet__dates">
            <label>
              Pick up
              <input
                type="datetime-local"
                max={searchForm.endTime}
                value={searchForm.startTime}
                onChange={(event) => setSearchForm((current) => ({ ...current, startTime: event.target.value }))}
              />
            </label>
            <label>
              Return
              <input
                type="datetime-local"
                min={searchForm.startTime}
                value={searchForm.endTime}
                onChange={(event) => setSearchForm((current) => ({ ...current, endTime: event.target.value }))}
              />
            </label>
          </div>
          {bookingWindowError ? <p className="filter-sheet__error">{bookingWindowError}</p> : null}
          <div className="filter-sheet__summary">
            {customerSummary ? (
              <p>
                {customerSummary.displayName} has {customerSummary.remainingHoursThisCycle.toFixed(1)}h remaining this cycle.
              </p>
            ) : (
              <p>Loading customer allowance summary.</p>
            )}
          </div>
          <button
            className="filter-sheet__apply"
            disabled={isBookingWindowInvalid}
            onClick={() => {
              setFilterOpen(false)
              void onSearch()
            }}
            type="button"
          >
            Apply and search
          </button>
        </div>
      </section>
    </div>
  )
}
