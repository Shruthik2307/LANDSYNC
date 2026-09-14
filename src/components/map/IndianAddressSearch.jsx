import React, { useState } from 'react'
import { Search, MapPin, X } from 'lucide-react'

export default function IndianAddressSearch({ onLocationSelect, onClose }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  // OpenStreetMap Nominatim API - Free, no API key needed
  // Focused on Indian locations
  const searchAddress = async (searchQuery) => {
    if (searchQuery.length < 3) {
      setResults([])
      return
    }

    setLoading(true)
    try {
      // Nominatim API with India bias
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?` +
        `format=json&` +
        `q=${encodeURIComponent(searchQuery)}&` +
        `countrycodes=in&` +
        `limit=5&` +
        `addressdetails=1`,
        {
          headers: {
            'User-Agent': 'LANDSYNC/1.0',
          },
        }
      )

      const data = await response.json()
      setResults(data)
    } catch (error) {
      console.error('Address search failed:', error)
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (e) => {
    const value = e.target.value
    setQuery(value)

    // Debounce search
    clearTimeout(window.addressSearchTimeout)
    window.addressSearchTimeout = setTimeout(() => {
      searchAddress(value)
    }, 300)
  }

  const handleSelect = (result) => {
    const location = {
      lat: parseFloat(result.lat),
      lng: parseFloat(result.lon),
      address: result.display_name,
      city: result.address?.city || result.address?.town || result.address?.village,
      state: result.address?.state,
      pincode: result.address?.postcode,
    }
    onLocationSelect(location)
    setQuery('')
    setResults([])
  }

  return (
    <div className="absolute top-20 left-3 right-3 sm:left-auto sm:w-96 z-[550] pointer-events-auto">
      {/* Search Input */}
      <div className="relative">
        <div className="relative">
          <Search
            size={18}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
          />
          <input
            type="text"
            value={query}
            onChange={handleSearch}
            placeholder="Search location in India..."
            className="w-full pl-10 pr-10 py-3 rounded-lg bg-[#070D1A]/95 backdrop-blur-xl border border-cyan-500/30 text-white placeholder-slate-400 text-sm focus:outline-none focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20 transition-all"
            autoFocus
          />
          {query && (
            <button
              onClick={() => {
                setQuery('')
                setResults([])
              }}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          )}
        </div>

        {/* Loading Indicator */}
        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Search Results Dropdown */}
      {results.length > 0 && (
        <div className="mt-2 rounded-lg bg-[#070D1A]/95 backdrop-blur-xl border border-cyan-500/30 shadow-2xl overflow-hidden animate-fadeIn">
          <div className="max-h-80 overflow-y-auto">
            {results.map((result, index) => (
              <button
                key={result.place_id || index}
                onClick={() => handleSelect(result)}
                className="w-full px-3 py-2.5 text-left hover:bg-cyan-500/10 border-b border-slate-800/50 last:border-b-0 transition-colors group"
              >
                <div className="flex items-start gap-2">
                  <MapPin
                    size={16}
                    className="text-cyan-400 mt-0.5 shrink-0"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-white font-medium truncate group-hover:text-cyan-300 transition-colors">
                      {result.address?.city || result.address?.town || result.address?.village || 'Location'}
                      {result.address?.state && `, ${result.address.state}`}
                    </div>
                    <div className="text-xs text-slate-400 truncate mt-0.5">
                      {result.display_name}
                    </div>
                    {result.address?.postcode && (
                      <div className="text-xs text-cyan-400/60 mt-0.5">
                        PIN: {result.address.postcode}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>

          {/* Powered by OSM */}
          <div className="px-3 py-1.5 bg-slate-950/50 border-t border-slate-800/50">
            <p className="text-[9px] text-slate-500 text-center">
              Powered by OpenStreetMap
            </p>
          </div>
        </div>
      )}

      {/* No Results */}
      {query.length >= 3 && !loading && results.length === 0 && (
        <div className="mt-2 px-4 py-3 rounded-lg bg-[#070D1A]/95 backdrop-blur-xl border border-slate-800/50 text-center">
          <p className="text-xs text-slate-400">
            No locations found. Try searching with city, state, or PIN code.
          </p>
        </div>
      )}

      {/* Quick Tips */}
      {query.length === 0 && (
        <div className="mt-2 px-3 py-2 rounded-lg bg-[#070D1A]/90 backdrop-blur-xl border border-slate-800/30">
          <p className="text-[10px] text-slate-400 mb-1 font-mono uppercase tracking-wider">
            Quick Tips:
          </p>
          <ul className="text-xs text-slate-400 space-y-0.5">
            <li>• Search by city, district, or state</li>
            <li>• Use PIN codes for accuracy</li>
            <li>• Include village/town names</li>
          </ul>
        </div>
      )}
    </div>
  )
}
