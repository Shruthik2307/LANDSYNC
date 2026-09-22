// Utility formatters and helper functions for FleetPulse

export const formatCurrency = (amount) => {
  if (amount === undefined || amount === null) return '₹0';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(amount);
};

export const formatNumber = (num) => {
  if (!num) return '0';
  return new Intl.NumberFormat('en-IN').format(num);
};

export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString;
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  }).format(date);
};

export const formatDateTime = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return dateString;
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};

export const getDaysRemaining = (expiryDateString) => {
  if (!expiryDateString) return 999;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const expiry = new Date(expiryDateString);
  expiry.setHours(0, 0, 0, 0);
  const diffTime = expiry.getTime() - today.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
};

export const getExpiryStatus = (expiryDateString) => {
  const days = getDaysRemaining(expiryDateString);
  if (days < 0) return { label: 'Expired', color: 'bg-red-500/20 text-red-400 border-red-500/40', badge: 'red' };
  if (days <= 30) return { label: `Expiring in ${days} days`, color: 'bg-amber-500/20 text-amber-400 border-amber-500/40', badge: 'amber' };
  return { label: 'Valid', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40', badge: 'emerald' };
};

export const getVehicleStatusColor = (status) => {
  switch (status) {
    case 'Available':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    case 'Assigned':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'On Trip':
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'Maintenance':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    case 'Inactive':
      return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
    default:
      return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  }
};

export const getTripStatusColor = (status) => {
  switch (status) {
    case 'Scheduled':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'Started':
      return 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30';
    case 'In Progress':
      return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
    case 'Completed':
      return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    case 'Cancelled':
      return 'bg-rose-500/20 text-rose-400 border-rose-500/30';
    default:
      return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  }
};

export const getIssueSeverityColor = (severity) => {
  switch (severity) {
    case 'Low':
      return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    case 'Medium':
      return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    case 'High':
      return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    case 'Critical':
      return 'bg-rose-500/20 text-rose-400 border-rose-500/30 animate-pulse';
    default:
      return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  }
};

export const exportToCSV = (filename, rows) => {
  if (!rows || !rows.length) return;
  const headers = Object.keys(rows[0]).join(',');
  const body = rows
    .map((row) =>
      Object.values(row)
        .map((val) => `"${String(val ?? '').replace(/"/g, '""')}"`)
        .join(',')
    )
    .join('\n');
  const csvContent = 'data:text/csv;charset=utf-8,' + encodeURIComponent(headers + '\n' + body);
  const link = document.createElement('a');
  link.setAttribute('href', csvContent);
  link.setAttribute('download', `${filename}_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
