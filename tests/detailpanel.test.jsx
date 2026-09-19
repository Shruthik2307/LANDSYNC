import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DetailPanel from '../src/components/result/DetailPanel.jsx'

vi.mock('../src/components/ui/ConfidenceDial', () => ({
  default: ({ value }) => <div data-testid="confidence-dial">{value}%</div>,
}))

describe('DetailPanel Component', () => {
  const mockParcel = {
    parcel_id: '1250',
    confidence: 68,
    priority: 'HIGH',
    area_difference: 31,
    geometry_conflict: true,
    attribute_conflict: true,
    duplicate_id: false,
    recommendation: 'Escalate for resurvey',
    attributes: {
      cadastral: {
        owner: 'Srinivas Reddy',
        area: 842.1,
        land_use: 'Agricultural',
        survey_date: '2016-07-22',
      },
      drone: {
        owner: 'Sreenivas Reddy',
        area: 873.2,
        land_use: 'Mixed Use',
        survey_date: '2025-12-05',
      },
    },
  }

  const mockOnClose = vi.fn()

  it('renders parcel details', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    expect(screen.getByText('1250')).toBeInTheDocument()
    expect(screen.getByText('HIGH PRIORITY')).toBeInTheDocument()
    expect(screen.getByText('31 m²')).toBeInTheDocument()
  })

  it('shows confidence dial with correct value', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    expect(screen.getByTestId('confidence-dial')).toHaveTextContent('68%')
  })

  it('displays geometry conflict message', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    // Issue text renders in both the Analysis Finding row and Recommended Action card
    expect(screen.getAllByText('Boundary shift detected').length).toBeGreaterThan(0)
  })

  it('displays attribute conflict message', () => {
    const attributeOnlyParcel = {
      ...mockParcel,
      geometry_conflict: false,
      attribute_conflict: true,
    }
    render(<DetailPanel parcel={attributeOnlyParcel} onClose={mockOnClose} />)
    expect(screen.getAllByText('Attribute mismatch detected').length).toBeGreaterThan(0)
  })

  it('displays duplicate ID badge when duplicate_id is true', () => {
    const duplicateParcel = { ...mockParcel, duplicate_id: true }
    render(<DetailPanel parcel={duplicateParcel} onClose={mockOnClose} />)
    expect(screen.getByText('DUPLICATE RECORD')).toBeInTheDocument()
  })

  it('shows side-by-side attribute comparison for conflicts', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    expect(screen.getByText('SOURCE ATTRIBUTE COMPARISON')).toBeInTheDocument()
    expect(screen.getByText('Cadastral/Revenue Record')).toBeInTheDocument()
    expect(screen.getByText('Drone/Municipal Record')).toBeInTheDocument()
    expect(screen.getByText('Srinivas Reddy')).toBeInTheDocument()
    expect(screen.getByText('Sreenivas Reddy')).toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    const closeButton = screen.getByLabelText('Close parcel details')
    fireEvent.click(closeButton)
    expect(mockOnClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when Escape key is pressed', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(mockOnClose).toHaveBeenCalled()
  })

  it('renders empty state when no parcel selected', () => {
    render(<DetailPanel parcel={null} onClose={mockOnClose} />)
    expect(
      screen.getByText('Select a parcel on the map or in the queue to inspect its reconciliation.')
    ).toBeInTheDocument()
  })

  it('shows recommendation text', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    expect(screen.getByText('Escalate for resurvey')).toBeInTheDocument()
  })

  it('displays area variance correctly', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    expect(screen.getByText('31 m²')).toBeInTheDocument()
  })

  it('shows Mismatch for geometry conflicts', () => {
    render(<DetailPanel parcel={mockParcel} onClose={mockOnClose} />)
    expect(screen.getByText('Mismatch')).toBeInTheDocument()
  })

  it('shows Consensus for no geometry conflicts', () => {
    const consensusParcel = { ...mockParcel, geometry_conflict: false }
    render(<DetailPanel parcel={consensusParcel} onClose={mockOnClose} />)
    expect(screen.getByText('Consensus')).toBeInTheDocument()
  })
})
