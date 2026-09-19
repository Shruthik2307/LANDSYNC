import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ParcelShape from '../src/components/map/ParcelShape.jsx'
import { computeDisputedRings } from '../src/components/map/disputedArea'

vi.mock('../src/components/map/disputedArea', () => ({
  computeDisputedRings: vi.fn(() => null),
}))

vi.mock('react-leaflet', () => ({
  CircleMarker: ({ children, eventHandlers }) => (
    <div data-testid="circle-marker" onClick={eventHandlers?.click}>
      {children}
    </div>
  ),
  Polygon: ({ eventHandlers, pathOptions }) => (
    <div
      data-testid="polygon"
      data-color={pathOptions.color}
      onClick={eventHandlers?.click}
    />
  ),
}))

vi.mock('@turf/difference', () => ({
  default: vi.fn(() => null),
}))

vi.mock('@turf/helpers', () => ({
  polygon: vi.fn((coords) => ({ type: 'Polygon', coordinates: coords })),
}))

describe('ParcelShape Component', () => {
  const mockParcel = {
    parcel_id: '1042',
    confidence: 87,
    priority: 'HIGH',
    geometry_conflict: true,
    attribute_conflict: false,
    boundaries: {
      cadastral: {
        type: 'Polygon',
        coordinates: [
          [
            [77.5941, 12.9716],
            [77.5962, 12.9716],
            [77.5962, 12.9734],
            [77.5941, 12.9734],
            [77.5941, 12.9716],
          ],
        ],
      },
      drone_ori: {
        type: 'Polygon',
        coordinates: [
          [
            [77.5944, 12.9713],
            [77.5966, 12.9717],
            [77.5961, 12.9736],
            [77.5942, 12.9732],
            [77.5944, 12.9713],
          ],
        ],
      },
    },
  }

  const mockOnSelect = vi.fn()

  it('renders cadastral polygon', () => {
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    expect(screen.getAllByTestId('polygon')).toHaveLength(1)
  })

  it('calls onSelect when parcel is clicked', () => {
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="both"
      />
    )
    const polygon = screen.getAllByTestId('polygon')[0]
    fireEvent.click(polygon)
    expect(mockOnSelect).toHaveBeenCalledWith(mockParcel)
  })

  it('renders with HIGH priority red color', () => {
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    const polygon = screen.getAllByTestId('polygon')[0]
    expect(polygon.dataset.color).toBe('#FF4C4C')
  })

  it('renders with MEDIUM priority amber color', () => {
    const mediumParcel = { ...mockParcel, priority: 'MEDIUM' }
    render(
      <ParcelShape
        parcel={mediumParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    const polygon = screen.getAllByTestId('polygon')[0]
    expect(polygon.dataset.color).toBe('#FFB800')
  })

  it('renders with LOW priority cyan color', () => {
    const lowParcel = { ...mockParcel, priority: 'LOW' }
    render(
      <ParcelShape
        parcel={lowParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    const polygon = screen.getAllByTestId('polygon')[0]
    expect(polygon.dataset.color).toBe('#00F0FF')
  })

  it('shows white stroke when selected', () => {
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={true}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    const polygon = screen.getAllByTestId('polygon')[0]
    expect(polygon.dataset.color).toBe('#FFFFFF')
  })

  it('returns null for invalid coordinates', () => {
    const invalidParcel = {
      ...mockParcel,
      boundaries: {
        cadastral: {
          coordinates: [[]],
        },
      },
    }
    const { container } = render(
      <ParcelShape
        parcel={invalidParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders circle marker at origin point', () => {
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={false}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="cadastral"
      />
    )
    expect(screen.getByTestId('circle-marker')).toBeInTheDocument()
  })

  it('renders the disputed-area overlay when selected with a geometry conflict', () => {
    computeDisputedRings.mockReturnValueOnce([
      [[12.9715, 77.5942], [12.9720, 77.5955], [12.9717, 77.5948]],
    ])
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={true}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="both"
      />
    )
    // 1 cadastral base + 1 disputed overlay + 2 boundary outlines (both mode)
    expect(screen.getAllByTestId('polygon')).toHaveLength(4)
    // Both full Polygon coordinate arrays must be handed to the geometry module
    expect(computeDisputedRings).toHaveBeenCalledWith(
      mockParcel.boundaries.cadastral.coordinates,
      mockParcel.boundaries.drone_ori.coordinates,
    )
  })

  it('omits the disputed-area overlay when no disputed rings are computed', () => {
    computeDisputedRings.mockReturnValueOnce(null)
    render(
      <ParcelShape
        parcel={mockParcel}
        selected={true}
        dimmed={false}
        onSelect={mockOnSelect}
        boundaryMode="both"
      />
    )
    // base + 2 boundary outlines only
    expect(screen.getAllByTestId('polygon')).toHaveLength(3)
  })
})
