import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App.jsx'

vi.mock('react-leaflet', () => ({
  CircleMarker: ({ children }) => <div data-testid="circle-marker">{children}</div>,
  MapContainer: ({ children }) => <div data-testid="map">{children}</div>,
  Polygon: () => <div data-testid="polygon" />,
  TileLayer: () => null,
  useMap: () => ({ fitBounds: vi.fn() }),
}))

vi.mock('../src/api.js', () => ({
  getConflicts: vi.fn(async () => [{ parcel_id: '<safe>', confidence: 80, priority: 'HIGH', area_difference: 3, geometry_conflict: false, attribute_conflict: true, duplicate_id: true, recommendation: '<verify>', boundaries: { cadastral: { type: 'Polygon', coordinates: [[[77.59, 12.97], [77.591, 12.97], [77.591, 12.971], [77.59, 12.971], [77.59, 12.97]]] } } }]),
  getParcels: vi.fn(async () => [{ parcel_id: '<safe>', confidence: 80, priority: 'HIGH', area_difference: 3, geometry_conflict: false, attribute_conflict: true, duplicate_id: true, recommendation: '<verify>', boundaries: { cadastral: { type: 'Polygon', coordinates: [[[77.59, 12.97], [77.591, 12.97], [77.591, 12.971], [77.59, 12.971], [77.59, 12.97]]] } } }]),
  getHealth: vi.fn(async () => ({ status: 'ok', engine: 'loaded', parcel_count: 25 })),
  isDemoMode: vi.fn(() => true),
  processDataset: vi.fn(async () => ({ job_status: 'complete' })),
  setDemoMode: vi.fn(),
  uploadDataset: vi.fn(async () => ({ dataset_id: 'test-dataset' })),
}))

describe('LANDSYNC screens', () => {
  beforeEach(() => vi.useRealTimers())

  // ArchitectureView is lazy-loaded behind Suspense; its one-time transform
  // cost (~1.2s, large lucide tree) can exceed findByText's default 1s window,
  // so poll generously and allow an above-default test timeout.
  it('keeps architecture available from upload and renders project boundaries', { timeout: 15000 }, async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: 'How it works' }))
    expect(await screen.findByText('Sources', {}, { timeout: 10000 })).toBeInTheDocument()
    expect(screen.getByText(/not a replacement for Bhuvan/)).toBeInTheDocument()
  })

  it('escapes hostile parcel strings and shows duplicate/attribute explanation', async () => {
    render(<App />)
    const input = document.querySelector('input[type="file"]')
    fireEvent.change(input, { target: { files: [new File(['x'], 'x.geojson')] } })
    fireEvent.click(screen.getByRole('button', { name: 'Process 1 source' }))
    await waitFor(() => expect(screen.getByText('Conflict Queue')).toBeInTheDocument())
    expect(screen.getAllByText('<safe>')).toHaveLength(2)
    expect(screen.getAllByText('Attribute mismatch detected')).toHaveLength(2)
    expect(screen.getByText('dup')).toBeInTheDocument()
    expect(screen.queryByText('<verify>')).toBeInTheDocument()
  })
})
