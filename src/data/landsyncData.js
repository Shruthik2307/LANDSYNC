// LANDSYNC — SIH26013 Multi-Source Geospatial Data & Shared Contract Models

export const SUPPORTED_DATA_SOURCES = [
  { id: 'drone_ori', name: 'Drone Imagery / ORI', type: 'Spatial / Visual', color: '#10b981', desc: 'High-resolution orthorectified imagery visual reference' },
  { id: 'cadastral', name: 'Cadastral Maps', type: 'Spatial Boundary', color: '#3b82f6', desc: 'Official parcel boundaries and survey geometry' },
  { id: 'revenue', name: 'Revenue Land Records', type: 'Non-Spatial Attributes', color: '#8b5cf6', desc: 'Ownership, katha, khata, land use, and legal attributes' },
  { id: 'municipal', name: 'Municipal GIS Layers', type: 'Urban Admin', color: '#f59e0b', desc: 'Urban planning zones, tax IDs, and civic boundaries' },
  { id: 'utility', name: 'Utility Network Data', type: 'Infrastructure', color: '#ec4899', desc: 'Underground pipelines, power lines, and right-of-way' },
  { id: 'ground_truthing', name: 'Ground Truthing (GT) GNSS', type: 'Field Reference', color: '#06b6d4', desc: 'Survey-grade GNSS/CORS physical verification points' },
  { id: 'building_footprints', name: 'Building Footprints (AI)', type: 'AI Feature Extraction', color: '#a855f7', desc: 'AI computer vision extracted structure outlines' }
];

export const INITIAL_PARCELS = [
  {
    parcel_id: "1042",
    survey_number: "204/A",
    village_name: "Kondapur",
    district: "Ranga Reddy",
    state: "Telangana",
    owner_name: "Sri Rajesh Kumar Verma",
    land_use: "Commercial / Mixed",
    area_cadastral_sqm: 1420,
    area_drone_sqm: 1444,
    area_difference: 24,
    geometry_conflict: true,
    attribute_conflict: false,
    topology_conflict: false,
    confidence: 87,
    priority: "HIGH",
    recommendation: "Field verification — 24m² area expansion & 3.2m boundary shift detected against Drone ORI.",
    sources_available: ["cadastral", "drone_ori", "revenue", "ground_truthing", "municipal"],
    coordinates: [
      [17.4475, 78.3750],
      [17.4478, 78.3762],
      [17.4468, 78.3765],
      [17.4465, 78.3752],
      [17.4475, 78.3750]
    ],
    drone_coordinates: [
      [17.44755, 78.37495],
      [17.44785, 78.37625],
      [17.4468, 78.3766],
      [17.4465, 78.3752],
      [17.44755, 78.37495]
    ],
    ground_truthing_points: [
      { id: "GT-1042-1", lat: 17.4475, lng: 78.3750, accuracy_cm: 2.1, timestamp: "2026-08-14" },
      { id: "GT-1042-2", lat: 17.4478, lng: 78.3762, accuracy_cm: 1.8, timestamp: "2026-08-14" },
      { id: "GT-1042-3", lat: 17.4468, lng: 78.3765, accuracy_cm: 2.4, timestamp: "2026-08-14" }
    ],
    attribute_comparison: {
      cadastral_owner: "Rajesh Kumar Verma",
      revenue_owner: "Rajesh K Verma",
      municipal_tax_id: "MUN-KND-9921",
      revenue_katha: "K-8812/2021"
    },
    conflict_summary: {
      geometry: "Boundary shift of 3.2m along North-East edge detected between Cadastral map and Drone ORI layer.",
      area: "Cadastral record lists 1420 m² vs Drone ORI measured area 1444 m² (+24 m² difference).",
      attribute: "Owner name matches with minor initials variation. Tax ID fully verified."
    }
  },
  {
    parcel_id: "1043",
    survey_number: "204/B",
    village_name: "Kondapur",
    district: "Ranga Reddy",
    state: "Telangana",
    owner_name: "Smt. Sunita Reddy",
    land_use: "Residential",
    area_cadastral_sqm: 850,
    area_drone_sqm: 852,
    area_difference: 2,
    geometry_conflict: false,
    attribute_conflict: false,
    topology_conflict: false,
    confidence: 98,
    priority: "LOW",
    recommendation: "Auto-Harmonized — High spatial & non-spatial agreement across all 5 data sources.",
    sources_available: ["cadastral", "drone_ori", "revenue", "ground_truthing", "municipal"],
    coordinates: [
      [17.4478, 78.3762],
      [17.4481, 78.3774],
      [17.4472, 78.3777],
      [17.4468, 78.3765],
      [17.4478, 78.3762]
    ],
    drone_coordinates: [
      [17.4478, 78.3762],
      [17.4481, 78.3774],
      [17.4472, 78.3777],
      [17.4468, 78.3765],
      [17.4478, 78.3762]
    ],
    ground_truthing_points: [
      { id: "GT-1043-1", lat: 17.4478, lng: 78.3762, accuracy_cm: 1.5, timestamp: "2026-08-14" },
      { id: "GT-1043-2", lat: 17.4481, lng: 78.3774, accuracy_cm: 1.2, timestamp: "2026-08-14" }
    ],
    attribute_comparison: {
      cadastral_owner: "Sunita Reddy",
      revenue_owner: "Sunita Reddy",
      municipal_tax_id: "MUN-KND-9922",
      revenue_katha: "K-8813/2021"
    },
    conflict_summary: {
      geometry: "No spatial disagreement. Geometries align cleanly within 0.1m tolerance.",
      area: "Area difference 2 m² (within standard 0.5% allowable margin).",
      attribute: "Perfect attribute match."
    }
  },
  {
    parcel_id: "1044",
    survey_number: "205/1",
    village_name: "Kondapur",
    district: "Ranga Reddy",
    state: "Telangana",
    owner_name: "M/S Green Infrastructure Ltd",
    land_use: "Industrial",
    area_cadastral_sqm: 3100,
    area_drone_sqm: 3280,
    area_difference: 180,
    geometry_conflict: true,
    attribute_conflict: true,
    topology_conflict: true,
    confidence: 62,
    priority: "HIGH",
    recommendation: "Field verification — Severe 180m² area mismatch, ownership attribute discrepancy, and utility easement encroachment.",
    sources_available: ["cadastral", "drone_ori", "revenue", "utility", "municipal", "building_footprints"],
    coordinates: [
      [17.4468, 78.3765],
      [17.4472, 78.3777],
      [17.4459, 78.3782],
      [17.4455, 78.3769],
      [17.4468, 78.3765]
    ],
    drone_coordinates: [
      [17.4469, 78.3764],
      [17.4473, 78.3779],
      [17.4458, 78.3784],
      [17.4454, 78.3768],
      [17.4469, 78.3764]
    ],
    ground_truthing_points: [],
    attribute_comparison: {
      cadastral_owner: "Green Infra Developers",
      revenue_owner: "AP Industrial Infrastructure Corp",
      municipal_tax_id: "MUN-KND-7711",
      revenue_katha: "K-4401/2018"
    },
    conflict_summary: {
      geometry: "Encroachment detected into municipal 12m buffer road & water pipeline easement.",
      area: "Major area mismatch of 180 m² (+5.8%).",
      attribute: "Owner discrepancy: Revenue record lists State Corp, Cadastral record lists Private Developer."
    }
  }
];

export const SYSTEM_METRICS_OVERVIEW = {
  total_parcels: 1420,
  reconciled_parcels: 1184,
  high_priority_queue: 86,
  medium_priority_queue: 150,
  auto_reconciliation_rate: 83.4,
  total_area_reconciled_sqkm: 18.4,
  interdept_sync_status: "Active (NAKSHA Sync v2.4)",
  last_drone_survey_date: "2026-08-28"
};