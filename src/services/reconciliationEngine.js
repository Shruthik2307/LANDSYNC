/**
 * LANDSYNC — AI Geospatial Reconciliation & Explainable Scoring Engine
 */

export function calculateStringSimilarity(str1, str2) {
  if (!str1 || !str2) return 0;
  const s1 = str1.toLowerCase().trim();
  const s2 = str2.toLowerCase().trim();
  if (s1 === s2) return 1.0;

  const len1 = s1.length;
  const len2 = s2.length;
  const matrix = Array(len1 + 1).fill(null).map(() => Array(len2 + 1).fill(null));

  for (let i = 0; i <= len1; i++) matrix[i][0] = i;
  for (let j = 0; j <= len2; j++) matrix[0][j] = j;

  for (let i = 1; i <= len1; i++) {
    for (let j = 1; j <= len2; j++) {
      const cost = s1[i - 1] === s2[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost
      );
    }
  }
  const distance = matrix[len1][len2];
  return Math.max(0, 1 - distance / Math.max(len1, len2));
}

export function calculateGeometryShiftMeters(coordsA, coordsB) {
  if (!coordsA || !coordsB || coordsA.length === 0 || coordsB.length === 0) return 0;
  let totalShift = 0;
  const count = Math.min(coordsA.length, coordsB.length);

  for (let i = 0; i < count; i++) {
    const latDiff = (coordsA[i][0] - coordsB[i][0]) * 111000;
    const lngDiff = (coordsA[i][1] - coordsB[i][1]) * 111000 * Math.cos(coordsA[i][0] * (Math.PI / 180));
    const dist = Math.sqrt(latDiff * latDiff + lngDiff * lngDiff);
    totalShift += dist;
  }
  return Number((totalShift / count).toFixed(2));
}

export function reconcileParcel(parcel) {
  const cadastralArea = parcel.area_cadastral_sqm || 0;
  const droneArea = parcel.area_drone_sqm || cadastralArea;
  const areaDiffSqm = Math.abs(cadastralArea - droneArea);
  const areaDiffPercent = cadastralArea > 0 ? (areaDiffSqm / cadastralArea) * 100 : 0;

  const shiftMeters = calculateGeometryShiftMeters(parcel.coordinates, parcel.drone_coordinates);
  let geometryScore = 100;
  if (shiftMeters > 5) geometryScore = 40;
  else if (shiftMeters > 2) geometryScore = 70;
  else if (shiftMeters > 0.5) geometryScore = 90;

  let areaScore = 100;
  if (areaDiffPercent > 10) areaScore = 30;
  else if (areaDiffPercent > 5) areaScore = 60;
  else if (areaDiffPercent > 2) areaScore = 85;

  const ownerCadastral = parcel.attribute_comparison?.cadastral_owner || parcel.owner_name || '';
  const ownerRevenue = parcel.attribute_comparison?.revenue_owner || parcel.owner_name || '';
  const attrSim = calculateStringSimilarity(ownerCadastral, ownerRevenue);
  const attributeScore = Math.round(attrSim * 100);

  const hasGroundTruthing = parcel.ground_truthing_points && parcel.ground_truthing_points.length > 0;
  const gtScore = hasGroundTruthing ? 100 : 70;

  const totalConfidence = Math.round(
    geometryScore * 0.40 +
    areaScore * 0.30 +
    attributeScore * 0.20 +
    gtScore * 0.10
  );

  const isGeometryConflict = shiftMeters > 1.5 || parcel.topology_conflict;
  const isAreaConflict = areaDiffPercent > 3.0;
  const isAttributeConflict = attributeScore < 85;

  let priority = "LOW";
  if (totalConfidence < 70 || isAttributeConflict || areaDiffPercent > 8) {
    priority = "HIGH";
  } else if (totalConfidence < 90 || isGeometryConflict || isAreaConflict) {
    priority = "MEDIUM";
  }

  let recommendation = "Auto-Harmonized — High multi-source spatial and attribute alignment.";
  if (priority === "HIGH") {
    if (isAttributeConflict) {
      recommendation = `Field verification — Ownership conflict (${ownerCadastral} vs ${ownerRevenue}) & ${areaDiffSqm}m² area variance.`;
    } else {
      recommendation = `Field verification — Critical boundary shift of ${shiftMeters}m & area discrepancy of ${areaDiffSqm}m².`;
    }
  } else if (priority === "MEDIUM") {
    recommendation = `Desk verification — Minor spatial shift of ${shiftMeters}m (${areaDiffSqm}m² area difference).`;
  }

  return {
    parcel_id: parcel.parcel_id,
    confidence: totalConfidence,
    priority: priority,
    area_difference: areaDiffSqm,
    geometry_conflict: isGeometryConflict,
    attribute_conflict: isAttributeConflict,
    topology_conflict: parcel.topology_conflict || false,
    recommendation: recommendation,
    score_breakdown: {
      geometry_score: geometryScore,
      area_score: areaScore,
      attribute_score: attributeScore,
      gt_verification_score: gtScore,
      boundary_shift_meters: shiftMeters,
      area_diff_percent: Number(areaDiffPercent.toFixed(1))
    }
  };
}

export function runBatchReconciliation(parcels) {
  return parcels.map(parcel => ({
    ...parcel,
    ...reconcileParcel(parcel)
  }));
}