import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  INITIAL_VEHICLES,
  INITIAL_DRIVERS,
  INITIAL_TRIPS,
  INITIAL_FUEL,
  INITIAL_MAINTENANCE,
  INITIAL_EXPENSES,
  INITIAL_DOCUMENTS,
  INITIAL_ISSUES,
  INITIAL_NOTIFICATIONS,
  INITIAL_AUDIT_LOGS
} from '../data/seedData';
import { useAuth } from './AuthContext';
import { getDaysRemaining } from '../utils/formatters';

const FleetContext = createContext();

export const FleetProvider = ({ children }) => {
  const { currentUser } = useAuth();

  const [vehicles, setVehicles] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_vehicles');
    return saved ? JSON.parse(saved) : INITIAL_VEHICLES;
  });

  const [drivers, setDrivers] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_drivers');
    return saved ? JSON.parse(saved) : INITIAL_DRIVERS;
  });

  const [trips, setTrips] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_trips');
    return saved ? JSON.parse(saved) : INITIAL_TRIPS;
  });

  const [fuel, setFuel] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_fuel');
    return saved ? JSON.parse(saved) : INITIAL_FUEL;
  });

  const [maintenance, setMaintenance] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_maintenance');
    return saved ? JSON.parse(saved) : INITIAL_MAINTENANCE;
  });

  const [expenses, setExpenses] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_expenses');
    return saved ? JSON.parse(saved) : INITIAL_EXPENSES;
  });

  const [documents, setDocuments] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_documents');
    return saved ? JSON.parse(saved) : INITIAL_DOCUMENTS;
  });

  const [issues, setIssues] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_issues');
    return saved ? JSON.parse(saved) : INITIAL_ISSUES;
  });

  const [notifications, setNotifications] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_notifications');
    return saved ? JSON.parse(saved) : INITIAL_NOTIFICATIONS;
  });

  const [auditLogs, setAuditLogs] = useState(() => {
    const saved = localStorage.getItem('fleetpulse_audit_logs');
    return saved ? JSON.parse(saved) : INITIAL_AUDIT_LOGS;
  });

  // Sync state to localStorage
  useEffect(() => { localStorage.setItem('fleetpulse_vehicles', JSON.stringify(vehicles)); }, [vehicles]);
  useEffect(() => { localStorage.setItem('fleetpulse_drivers', JSON.stringify(drivers)); }, [drivers]);
  useEffect(() => { localStorage.setItem('fleetpulse_trips', JSON.stringify(trips)); }, [trips]);
  useEffect(() => { localStorage.setItem('fleetpulse_fuel', JSON.stringify(fuel)); }, [fuel]);
  useEffect(() => { localStorage.setItem('fleetpulse_maintenance', JSON.stringify(maintenance)); }, [maintenance]);
  useEffect(() => { localStorage.setItem('fleetpulse_expenses', JSON.stringify(expenses)); }, [expenses]);
  useEffect(() => { localStorage.setItem('fleetpulse_documents', JSON.stringify(documents)); }, [documents]);
  useEffect(() => { localStorage.setItem('fleetpulse_issues', JSON.stringify(issues)); }, [issues]);
  useEffect(() => { localStorage.setItem('fleetpulse_notifications', JSON.stringify(notifications)); }, [notifications]);
  useEffect(() => { localStorage.setItem('fleetpulse_audit_logs', JSON.stringify(auditLogs)); }, [auditLogs]);

  // Helper to log audit trail
  const logAuditAction = (action, entity, entityId, details) => {
    const newLog = {
      id: `AUD-${Date.now().toString().slice(-4)}`,
      userId: currentUser?.id || 'USR-SYS',
      userName: `${currentUser?.name || 'System User'} (${currentUser?.role || 'Admin'})`,
      action,
      entity,
      entityId,
      details,
      timestamp: new Date().toISOString().replace('T', ' ').slice(0, 16)
    };
    setAuditLogs((prev) => [newLog, ...prev]);
  };

  // Helper to create notifications
  const pushNotification = (title, message, type = 'Alert', category = 'System') => {
    const newNtf = {
      id: `NTF-${Date.now().toString().slice(-4)}`,
      title,
      message,
      type,
      category,
      read: false,
      timestamp: new Date().toISOString().replace('T', ' ').slice(0, 16)
    };
    setNotifications((prev) => [newNtf, ...prev]);
  };

  // Check document expiries on mount
  useEffect(() => {
    documents.forEach((doc) => {
      const days = getDaysRemaining(doc.expiryDate);
      if (days <= 30 && days >= 0) {
        const title = `${doc.docType} Expiring Soon`;
        const exists = notifications.some((n) => n.title === title && n.message.includes(doc.docNumber));
        if (!exists) {
          pushNotification(title, `Document ${doc.docNumber} (${doc.docType}) expires in ${days} days.`, days <= 7 ? 'Critical' : 'Alert', 'Document');
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional mount-only scan; adding deps would re-notify on every update
  }, []);

  // CRUD for Vehicles
  const addVehicle = (vehicleData) => {
    const id = `VEH-${(vehicles.length + 1).toString().padStart(2, '0')}`;
    const newVehicle = { id, status: 'Available', currentOdometer: Number(vehicleData.currentOdometer || 0), ...vehicleData };
    setVehicles((prev) => [newVehicle, ...prev]);
    logAuditAction('CREATE_VEHICLE', 'Vehicle', id, `Added vehicle ${newVehicle.regNo} (${newVehicle.make} ${newVehicle.model})`);
    pushNotification('New Vehicle Registered', `Vehicle ${newVehicle.regNo} has been added to the fleet.`, 'Alert', 'Fleet');
    return newVehicle;
  };

  const updateVehicle = (id, updatedFields) => {
    setVehicles((prev) =>
      prev.map((v) => (v.id === id ? { ...v, ...updatedFields } : v))
    );
    logAuditAction('UPDATE_VEHICLE', 'Vehicle', id, `Updated vehicle details for ${id}`);
  };

  const deleteVehicle = (id) => {
    const target = vehicles.find((v) => v.id === id);
    setVehicles((prev) => prev.filter((v) => v.id !== id));
    logAuditAction('DELETE_VEHICLE', 'Vehicle', id, `Deleted vehicle ${target?.regNo || id}`);
  };

  // CRUD for Drivers
  const addDriver = (driverData) => {
    const id = `DRV-${(drivers.length + 1).toString().padStart(2, '0')}`;
    const newDriver = { id, status: 'Available', totalTrips: 0, rating: 5.0, ...driverData };
    setDrivers((prev) => [newDriver, ...prev]);
    logAuditAction('CREATE_DRIVER', 'Driver', id, `Added driver ${newDriver.fullName} (${newDriver.licenseNo})`);
    return newDriver;
  };

  const updateDriver = (id, updatedFields) => {
    setDrivers((prev) =>
      prev.map((d) => (d.id === id ? { ...d, ...updatedFields } : d))
    );
    logAuditAction('UPDATE_DRIVER', 'Driver', id, `Updated driver profile for ${id}`);
  };

  const assignDriverToVehicle = (driverId, vehicleId) => {
    setVehicles((prev) =>
      prev.map((v) => {
        if (v.id === vehicleId) return { ...v, assignedDriverId: driverId, status: v.status === 'Available' ? 'Assigned' : v.status };
        if (v.assignedDriverId === driverId && v.id !== vehicleId) return { ...v, assignedDriverId: null };
        return v;
      })
    );
    setDrivers((prev) =>
      prev.map((d) => (d.id === driverId ? { ...d, assignedVehicleId: vehicleId, status: 'Assigned' } : d))
    );
    logAuditAction('ASSIGN_DRIVER', 'Driver', driverId, `Assigned driver ${driverId} to vehicle ${vehicleId}`);
  };

  // CRUD for Trips & Workflow
  const addTrip = (tripData) => {
    const id = `TRP-${1000 + trips.length + 1}`;
    const distanceKm = tripData.distanceKm || (tripData.endOdometer ? tripData.endOdometer - tripData.startOdometer : 0);
    const revenue = Number(tripData.revenue || 0);
    const tripExpenses = Number(tripData.expenses || 0);

    const newTrip = {
      id,
      status: 'Scheduled',
      actualArrival: null,
      endOdometer: null,
      fuelUsedLitres: 0,
      revenue,
      expenses: tripExpenses,
      distanceKm,
      ...tripData
    };

    setTrips((prev) => [newTrip, ...prev]);

    // Update vehicle & driver status to Assigned or On Trip if starting
    if (newTrip.vehicleId) {
      updateVehicle(newTrip.vehicleId, { status: 'Assigned' });
    }
    if (newTrip.driverId) {
      updateDriver(newTrip.driverId, { status: 'Assigned' });
    }

    logAuditAction('CREATE_TRIP', 'Trip', id, `Created trip ${id} (${newTrip.startLocation} ➔ ${newTrip.destination})`);
    return newTrip;
  };

  const updateTripStatus = (tripId, nextStatus, payload = {}) => {
    let targetTrip = trips.find((t) => t.id === tripId);
    if (!targetTrip) return;

    const updatedTrip = { ...targetTrip, status: nextStatus, ...payload };

    if (nextStatus === 'Started' || nextStatus === 'In Progress') {
      if (updatedTrip.vehicleId) updateVehicle(updatedTrip.vehicleId, { status: 'On Trip' });
      if (updatedTrip.driverId) updateDriver(updatedTrip.driverId, { status: 'On Trip' });
    } else if (nextStatus === 'Completed' || nextStatus === 'Cancelled') {
      const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 16);
      if (nextStatus === 'Completed') {
        updatedTrip.actualArrival = nowStr;
        if (payload.endOdometer && updatedTrip.startOdometer) {
          updatedTrip.distanceKm = Number(payload.endOdometer) - Number(updatedTrip.startOdometer);
        }
      }

      if (updatedTrip.vehicleId) {
        updateVehicle(updatedTrip.vehicleId, {
          status: 'Available',
          currentOdometer: payload.endOdometer ? Number(payload.endOdometer) : vehicles.find(v => v.id === updatedTrip.vehicleId)?.currentOdometer
        });
      }
      if (updatedTrip.driverId) {
        setDrivers((prev) =>
          prev.map((d) =>
            d.id === updatedTrip.driverId ? { ...d, status: 'Available', totalTrips: (d.totalTrips || 0) + 1 } : d
          )
        );
      }
    }

    setTrips((prev) => prev.map((t) => (t.id === tripId ? updatedTrip : t)));
    logAuditAction('UPDATE_TRIP_STATUS', 'Trip', tripId, `Changed status of ${tripId} to ${nextStatus}`);
    pushNotification(`Trip ${nextStatus}`, `Trip ${tripId} has been marked as ${nextStatus}.`, 'Alert', 'Trip');
  };

  // CRUD for Fuel
  const addFuelRecord = (fuelData) => {
    const id = `FUL-${500 + fuel.length + 1}`;
    const litres = Number(fuelData.litres || 0);
    const pricePerLitre = Number(fuelData.pricePerLitre || 0);
    const totalCost = fuelData.totalCost ? Number(fuelData.totalCost) : litres * pricePerLitre;

    const newRecord = { id, litres, pricePerLitre, totalCost, ...fuelData };
    setFuel((prev) => [newRecord, ...prev]);

    // Also auto-record an expense record
    addExpense({
      vehicleId: newRecord.vehicleId,
      driverId: newRecord.driverId,
      category: 'Fuel',
      amount: totalCost,
      date: newRecord.date,
      paymentMethod: 'Company Card / Fuel Card',
      vendor: newRecord.fuelStation,
      receiptPhoto: newRecord.receiptPhoto,
      description: `Fuel fill up ${litres}L @ ₹${pricePerLitre}/L (${newRecord.fuelStation})`
    });

    // Check abnormal fuel consumption
    if (newRecord.vehicleId && newRecord.odometer) {
      updateVehicle(newRecord.vehicleId, { currentOdometer: Number(newRecord.odometer) });
    }

    logAuditAction('LOG_FUEL', 'Fuel', id, `Logged fuel purchase ₹${totalCost} (${litres}L) for vehicle ${newRecord.vehicleId}`);
    return newRecord;
  };

  // CRUD for Maintenance
  const addMaintenanceRecord = (mntData) => {
    const id = `MNT-${800 + maintenance.length + 1}`;
    const labourCost = Number(mntData.labourCost || 0);
    const partsCost = Number(mntData.partsCost || 0);
    const totalCost = mntData.totalCost ? Number(mntData.totalCost) : labourCost + partsCost;

    const newRecord = { id, labourCost, partsCost, totalCost, status: 'Scheduled', ...mntData };
    setMaintenance((prev) => [newRecord, ...prev]);

    if (mntData.vehicleId) {
      updateVehicle(mntData.vehicleId, {
        status: mntData.status === 'In Progress' ? 'Maintenance' : vehicles.find(v => v.id === mntData.vehicleId)?.status,
        nextServiceDate: mntData.nextServiceDate || vehicles.find(v => v.id === mntData.vehicleId)?.nextServiceDate
      });
    }

    addExpense({
      vehicleId: mntData.vehicleId,
      driverId: null,
      category: 'Maintenance',
      amount: totalCost,
      date: mntData.date,
      paymentMethod: 'Bank Transfer / Cheque',
      vendor: mntData.serviceProvider,
      receiptPhoto: mntData.invoicePhoto,
      description: `Service: ${mntData.serviceType} at ${mntData.serviceProvider}`
    });

    logAuditAction('LOG_MAINTENANCE', 'Maintenance', id, `Logged service ₹${totalCost} for vehicle ${mntData.vehicleId}`);
    pushNotification('Maintenance Service Scheduled', `Service ${mntData.serviceType} scheduled for ${mntData.vehicleId}.`, 'Warning', 'Maintenance');
    return newRecord;
  };

  // CRUD for Expenses
  const addExpense = (expData) => {
    const id = `EXP-${300 + expenses.length + 1}`;
    const newExp = { id, amount: Number(expData.amount || 0), ...expData };
    setExpenses((prev) => [newExp, ...prev]);
    logAuditAction('LOG_EXPENSE', 'Expense', id, `Logged expense ₹${newExp.amount} (${newExp.category})`);
    return newExp;
  };

  // CRUD for Documents
  const addDocument = (docData) => {
    const id = `DOC-${100 + documents.length + 1}`;
    const newDoc = { id, ...docData };
    setDocuments((prev) => [newDoc, ...prev]);

    // Update vehicle/driver expiry dates if matching
    if (newDoc.entityType === 'Vehicle' && newDoc.entityId) {
      if (newDoc.docType.includes('Insurance')) updateVehicle(newDoc.entityId, { insuranceExpiry: newDoc.expiryDate });
      if (newDoc.docType.includes('Permit')) updateVehicle(newDoc.entityId, { permitExpiry: newDoc.expiryDate });
      if (newDoc.docType.includes('Pollution')) updateVehicle(newDoc.entityId, { pollutionExpiry: newDoc.expiryDate });
    } else if (newDoc.entityType === 'Driver' && newDoc.entityId) {
      if (newDoc.docType.includes('License')) updateDriver(newDoc.entityId, { licenseExpiry: newDoc.expiryDate });
    }

    logAuditAction('UPLOAD_DOCUMENT', 'Document', id, `Uploaded ${newDoc.docType} (${newDoc.docNumber})`);
    pushNotification('Document Uploaded', `${newDoc.docType} uploaded successfully for ${newDoc.entityId}.`, 'Alert', 'Document');
    return newDoc;
  };

  // CRUD for Issues & Driver Defect Reporting
  const addIssue = (issueData) => {
    const id = `ISS-${700 + issues.length + 1}`;
    const reportedAt = new Date().toISOString().replace('T', ' ').slice(0, 16);
    const newIssue = { id, status: 'Reported', reportedAt, ...issueData };
    setIssues((prev) => [newIssue, ...prev]);

    const isHigh = newIssue.severity === 'High' || newIssue.severity === 'Critical';
    if (isHigh) {
      pushNotification(
        `CRITICAL ISSUE: ${newIssue.category}`,
        `Vehicle ${newIssue.vehicleId} reported severe issue: "${newIssue.description}". Immediate manager action required!`,
        'Critical',
        'Issue'
      );
    }

    logAuditAction('REPORT_ISSUE', 'VehicleIssue', id, `Driver reported ${newIssue.severity} issue on vehicle ${newIssue.vehicleId}`);
    return newIssue;
  };

  const updateIssueStatus = (issueId, status, notes = '') => {
    setIssues((prev) =>
      prev.map((iss) => (iss.id === issueId ? { ...iss, status, notes: notes || iss.notes } : iss))
    );

    const target = issues.find((i) => i.id === issueId);
    if (status === 'In Repair' && target?.vehicleId) {
      updateVehicle(target.vehicleId, { status: 'Maintenance' });
    } else if (status === 'Resolved' && target?.vehicleId) {
      updateVehicle(target.vehicleId, { status: 'Available' });
    }

    logAuditAction('RESOLVE_ISSUE', 'VehicleIssue', issueId, `Updated issue ${issueId} status to ${status}`);
  };

  const markNotificationAsRead = (id) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const markAllNotificationsAsRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  };

  const resetToSeedData = () => {
    setVehicles(INITIAL_VEHICLES);
    setDrivers(INITIAL_DRIVERS);
    setTrips(INITIAL_TRIPS);
    setFuel(INITIAL_FUEL);
    setMaintenance(INITIAL_MAINTENANCE);
    setExpenses(INITIAL_EXPENSES);
    setDocuments(INITIAL_DOCUMENTS);
    setIssues(INITIAL_ISSUES);
    setNotifications(INITIAL_NOTIFICATIONS);
    setAuditLogs(INITIAL_AUDIT_LOGS);
    localStorage.clear();
    logAuditAction('RESET_SYSTEM', 'System', 'ALL', 'Reset all database stores to initial demo dataset');
  };

  return (
    <FleetContext.Provider
      value={{
        vehicles,
        drivers,
        trips,
        fuel,
        maintenance,
        expenses,
        documents,
        issues,
        notifications,
        auditLogs,
        addVehicle,
        updateVehicle,
        deleteVehicle,
        addDriver,
        updateDriver,
        assignDriverToVehicle,
        addTrip,
        updateTripStatus,
        addFuelRecord,
        addMaintenanceRecord,
        addExpense,
        addDocument,
        addIssue,
        updateIssueStatus,
        markNotificationAsRead,
        markAllNotificationsAsRead,
        resetToSeedData
      }}
    >
      {children}
    </FleetContext.Provider>
  );
};

export const useFleet = () => {
  const context = useContext(FleetContext);
  if (!context) {
    throw new Error('useFleet must be used within a FleetProvider');
  }
  return context;
};
