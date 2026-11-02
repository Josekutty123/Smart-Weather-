/**
 * Smart Weather Monitoring System - Dashboard Controller
 * Real-time telemetry ingestion, level categorization, interactive charts, and farmer alerts.
 */

// ============================================================
// 1. Central Configurable Thresholds
// ============================================================
const WEATHER_THRESHOLDS = {
    temperature: {
        lowMax: 20.0,    // Below 20°C: LOW | 20°C to 35°C: MEDIUM | Above 35°C: HIGH
        medMax: 35.0     
    },
    humidity: {
        lowMax: 40.0,    // Below 40%: LOW  | 40% to 70%: MEDIUM   | Above 70%: HIGH
        medMax: 70.0     
    }
};

let currentChartRange = '1h'; // Default chart time range: 1 Hour
let latestTelemetryCache = null;

// ============================================================
// 2. Helper Functions: Categorization & Status
// ============================================================

/**
 * Determine Temperature Category (LOW, MEDIUM, HIGH)
 * LOW: Blue (<20°C) | MEDIUM: Green (20-35°C) | HIGH: Red (>35°C)
 */
function getTemperatureCategory(temp) {
    if (temp === null || isNaN(temp)) {
        return { label: '--', badgeClass: 'bg-secondary text-white' };
    }
    if (temp < WEATHER_THRESHOLDS.temperature.lowMax) {
        return { label: 'LOW', badgeClass: 'bg-primary text-white' }; // Blue
    } else if (temp <= WEATHER_THRESHOLDS.temperature.medMax) {
        return { label: 'MEDIUM', badgeClass: 'bg-success text-white' }; // Green
    } else {
        return { label: 'HIGH', badgeClass: 'bg-danger text-white' }; // Red
    }
}

/**
 * Determine Humidity Category (LOW, MEDIUM, HIGH)
 * LOW: Blue (<40%) | MEDIUM: Green (40-70%) | HIGH: Red (>70%)
 */
function getHumidityCategory(hum) {
    if (hum === null || isNaN(hum)) {
        return { label: '--', badgeClass: 'bg-secondary text-white' };
    }
    if (hum < WEATHER_THRESHOLDS.humidity.lowMax) {
        return { label: 'LOW', badgeClass: 'bg-primary text-white' }; // Blue
    } else if (hum <= WEATHER_THRESHOLDS.humidity.medMax) {
        return { label: 'MEDIUM', badgeClass: 'bg-success text-white' }; // Green
    } else {
        return { label: 'HIGH', badgeClass: 'bg-danger text-white' }; // Red
    }
}

/**
 * Determine Rain status based on digital plate sensor
 */
function getRainStatus(reading) {
    if (!reading) {
        return { label: 'NO DATA', isRain: false, raw: '--' };
    }
    const isDetected = Boolean(reading.rain_detected);
    const rawVal = reading.rain_value !== undefined ? reading.rain_value : '--';
    
    return {
        label: isDetected ? 'RAIN DETECTED' : 'NO RAIN',
        isRain: isDetected,
        raw: rawVal
    };
}

// ============================================================
// 3. Main Initialization & Event Listeners
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    // Initial data fetches
    fetchLatestData();
    fetchHistoryData(currentChartRange);

    // Setup polling: Real-time cards every 3 seconds
    setInterval(() => {
        fetchLatestData();
    }, 3000);

    // Setup polling: Charts and history logs every 10 seconds
    setInterval(() => {
        fetchHistoryData(currentChartRange);
    }, 10000);

    // Setup UI event listeners
    setupUIListeners();
});

function setupUIListeners() {
    // Mobile Sidebar Toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    const appSidebar = document.getElementById('appSidebar');
    const sidebarBackdrop = document.getElementById('sidebarBackdrop');

    if (sidebarToggle && appSidebar) {
        sidebarToggle.addEventListener('click', () => {
            appSidebar.classList.toggle('show');
            if (sidebarBackdrop) sidebarBackdrop.classList.toggle('show');
        });
    }

    if (sidebarBackdrop && appSidebar) {
        sidebarBackdrop.addEventListener('click', () => {
            appSidebar.classList.remove('show');
            sidebarBackdrop.classList.remove('show');
        });
    }

    // Chart Time Range Selector Buttons
    document.querySelectorAll('.time-range-group .btn-range').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.time-range-group .btn-range').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentChartRange = e.target.dataset.range || '1h';
            fetchHistoryData(currentChartRange);
        });
    });

    // Close mobile sidebar on link click
    document.querySelectorAll('.sidebar-nav .nav-link').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 992 && appSidebar && sidebarBackdrop) {
                appSidebar.classList.remove('show');
                sidebarBackdrop.classList.remove('show');
            }
        });
    });
}

// ============================================================
// 4. Fetch Latest Telemetry & Update UI Cards
// ============================================================
async function fetchLatestData() {
    try {
        const response = await fetch('/api/sensor-data/latest');
        const data = await response.json();

        if (data.status !== 'success') return;
        latestTelemetryCache = data;

        const noDataNotice = document.getElementById('no-data-notice');
        const deviceStatusBadge = document.getElementById('device-status-badge');
        const deviceStatusText = document.getElementById('device-status-text');
        const valLastSeenHeader = document.getElementById('val-last-seen-header');
        const valLastSeenCard = document.getElementById('val-last-seen-card');
        const valDeviceState = document.getElementById('val-device-state');
        const sidebarPulseDot = document.getElementById('sidebar-pulse-dot');
        const sidebarNodeStatus = document.getElementById('sidebar-node-status');
        const sidebarNodeId = document.getElementById('sidebar-node-id');

        // 1. ESP32 Connection Status
        const isOnline = data.device && data.device.is_online;
        const deviceId = data.device && data.device.device_id ? data.device.device_id : 'ESP32_FARM_01';
        if (sidebarNodeId) sidebarNodeId.innerText = deviceId;

        if (isOnline) {
            deviceStatusBadge.className = 'badge bg-success connection-badge d-flex align-items-center gap-1';
            deviceStatusText.innerText = 'ESP32 ONLINE';
            valDeviceState.innerText = 'ONLINE';
            valDeviceState.className = 'card-value mb-0 fs-3 text-success';
            if (sidebarPulseDot) sidebarPulseDot.className = 'status-pulse-dot online';
            if (sidebarNodeStatus) sidebarNodeStatus.innerText = 'Connected & Active';
        } else {
            deviceStatusBadge.className = 'badge bg-secondary connection-badge d-flex align-items-center gap-1';
            deviceStatusText.innerText = 'ESP32 OFFLINE';
            valDeviceState.innerText = 'OFFLINE';
            valDeviceState.className = 'card-value mb-0 fs-3 text-secondary';
            if (sidebarPulseDot) sidebarPulseDot.className = 'status-pulse-dot';
            if (sidebarNodeStatus) sidebarNodeStatus.innerText = 'Disconnected';
        }

        // 2. Sensor Readings Update
        const reading = data.reading;
        if (reading) {
            if (noDataNotice) noDataNotice.classList.add('d-none');

            // Format timestamp
            const recordedAt = reading.recorded_at || 'Just now';
            const timePart = recordedAt.split(' ').length > 1 ? recordedAt.split(' ')[1] : recordedAt;
            if (valLastSeenHeader) valLastSeenHeader.innerText = `Sync: ${timePart}`;
            if (valLastSeenCard) valLastSeenCard.innerText = `Last data: ${recordedAt}`;

            // Temperature
            const tempVal = parseFloat(reading.temperature);
            document.getElementById('val-temperature').innerText = `${tempVal.toFixed(1)} °C`;
            const tempCat = getTemperatureCategory(tempVal);
            const tempBadge = document.getElementById('badge-temp-category');
            if (tempBadge) {
                tempBadge.innerText = tempCat.label;
                tempBadge.className = `badge ${tempCat.badgeClass} category-badge`;
            }

            // Humidity
            const humVal = parseFloat(reading.humidity);
            document.getElementById('val-humidity').innerText = `${humVal.toFixed(1)} %`;
            const humCat = getHumidityCategory(humVal);
            const humBadge = document.getElementById('badge-hum-category');
            if (humBadge) {
                humBadge.innerText = humCat.label;
                humBadge.className = `badge ${humCat.badgeClass} category-badge`;
            }

            // Rain Monitoring
            const rainStatus = getRainStatus(reading);
            const valRainStatus = document.getElementById('val-rain-status');
            const valRainRaw = document.getElementById('val-rain-raw');
            const rainIcon = document.getElementById('rain-card-icon');
            const rainIconBox = document.getElementById('rain-icon-box');

            if (valRainStatus) {
                valRainStatus.innerText = rainStatus.label;
                valRainStatus.className = `card-value mb-0 ${rainStatus.isRain ? 'text-primary' : 'text-dark'}`;
            }
            if (valRainRaw) {
                valRainRaw.innerText = `Raw: ${rainStatus.raw}`;
            }
            if (rainIcon) {
                rainIcon.className = rainStatus.isRain ? 'bi bi-cloud-rain-fill text-primary' : 'bi bi-cloud-sun text-secondary';
            }
            if (rainIconBox) {
                rainIconBox.style.backgroundColor = rainStatus.isRain ? '#cff4fc' : '#e0f7fa';
            }

            // 3. Update Farmer Alerts
            updateFarmerAlerts(tempVal, humVal, rainStatus.isRain);

        } else {
            // No telemetry yet
            if (noDataNotice) noDataNotice.classList.remove('d-none');
            document.getElementById('val-temperature').innerText = '-- °C';
            document.getElementById('val-humidity').innerText = '-- %';
            document.getElementById('val-rain-status').innerText = 'NO RAIN';
            if (valLastSeenHeader) valLastSeenHeader.innerText = 'Sync: Waiting...';
            if (valLastSeenCard) valLastSeenCard.innerText = 'Last data: Waiting...';
            updateFarmerAlerts(null, null, false);
        }

    } catch (err) {
        console.warn('Telemetry fetch error:', err);
    }
}

// ============================================================
// 5. Farmer Alerts Evaluation & Display
// ============================================================
function updateFarmerAlerts(temp, hum, isRain) {
    const alertContainer = document.getElementById('active-alerts-container');
    const alertHeaderIcon = document.getElementById('alert-header-icon');
    const alertHeaderBox = document.getElementById('alert-header-icon-box');
    const alertStatusBadge = document.getElementById('alert-status-badge');
    const sidebarAlertBadge = document.getElementById('sidebar-alert-badge');

    if (!alertContainer) return;

    const activeAlerts = [];

    // 1. High Temperature Alert (> 35°C)
    if (temp !== null && temp > WEATHER_THRESHOLDS.temperature.medMax) {
        activeAlerts.push({
            type: 'warning',
            icon: 'bi-exclamation-triangle-fill text-danger',
            title: 'High Field Temperature Alert',
            message: `Temperature reached ${temp.toFixed(1)} °C (High). Watch for crop heat stress; ensure adequate irrigation.`
        });
    }

    // 2. High Humidity Alert (> 70%)
    if (hum !== null && hum > WEATHER_THRESHOLDS.humidity.medMax) {
        activeAlerts.push({
            type: 'warning',
            icon: 'bi-droplet-fill text-warning',
            title: 'High Humidity Alert',
            message: `Relative humidity is ${hum.toFixed(1)} % (High). Elevated moisture increases fungal disease risk; postpone chemical spraying.`
        });
    }

    // 3. Rain Detected Alert
    if (isRain) {
        activeAlerts.push({
            type: 'info',
            icon: 'bi-cloud-rain-fill text-primary',
            title: 'Precipitation Alert',
            message: 'Rainfall detected on the field sensor plate. Pause active irrigation channels.'
        });
    }

    // Update Sidebar Alert Count Badge
    if (sidebarAlertBadge) {
        if (activeAlerts.length > 0) {
            sidebarAlertBadge.innerText = activeAlerts.length;
            sidebarAlertBadge.classList.remove('d-none');
        } else {
            sidebarAlertBadge.classList.add('d-none');
        }
    }

    // Render Alerts or Optimal State
    if (activeAlerts.length === 0) {
        if (alertHeaderIcon) alertHeaderIcon.className = 'bi bi-shield-check text-success';
        if (alertHeaderBox) alertHeaderBox.style.backgroundColor = '#dcfce7';
        if (alertStatusBadge) {
            alertStatusBadge.className = 'badge bg-success-subtle text-success border border-success px-2 py-1';
            alertStatusBadge.innerText = 'Conditions Optimal';
        }

        alertContainer.innerHTML = `
            <div class="alert-pill alert-pill-success d-flex align-items-center gap-2">
                <i class="bi bi-check-circle-fill text-success fs-5"></i>
                <span>All field parameters are within normal safety thresholds. No active weather hazard.</span>
            </div>
        `;
    } else {
        if (alertHeaderIcon) alertHeaderIcon.className = 'bi bi-exclamation-circle-fill text-danger';
        if (alertHeaderBox) alertHeaderBox.style.backgroundColor = '#fee2e2';
        if (alertStatusBadge) {
            alertStatusBadge.className = 'badge bg-danger text-white px-2 py-1';
            alertStatusBadge.innerText = `${activeAlerts.length} Active Alert${activeAlerts.length > 1 ? 's' : ''}`;
        }

        alertContainer.innerHTML = activeAlerts.map(a => `
            <div class="alert-pill ${a.type === 'info' ? 'alert-pill-info' : 'alert-pill-warning'} d-flex align-items-center gap-2">
                <i class="bi ${a.icon} fs-5"></i>
                <div>
                    <strong>${a.title}:</strong> ${a.message}
                </div>
            </div>
        `).join('');
    }
}

// ============================================================
// 6. Fetch Historical Sensor Readings & Update Charts + Table
// ============================================================
async function fetchHistoryData(rangeKey) {
    try {
        const response = await fetch(`/api/sensor-data/history?range=${rangeKey || '1h'}`);
        const data = await response.json();

        if (data.status !== 'success') return;
        const readings = data.readings || [];

        // 1. Update the 3 Interactive Chart.js Graphs
        if (typeof updateAllCharts === 'function') {
            updateAllCharts(readings);
        }

        // 2. Update Recent 5 Readings Table
        updateRecentTable(readings);

    } catch (err) {
        console.warn('History fetch error:', err);
    }
}

/**
 * Render the Latest 5 Telemetry Rows in Table
 */
function updateRecentTable(readings) {
    const tableBody = document.getElementById('recent-table-body');
    if (!tableBody) return;

    if (!readings || readings.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-muted py-4">Waiting for sensor data from ESP32...</td></tr>';
        return;
    }

    // Get the latest 5 records in reverse chronological order
    const latest5 = [...readings].reverse().slice(0, 5);

    tableBody.innerHTML = latest5.map(r => {
        const tempVal = parseFloat(r.temperature);
        const humVal = parseFloat(r.humidity);
        const tempCat = getTemperatureCategory(tempVal);
        const humCat = getHumidityCategory(humVal);
        const rainStatus = getRainStatus(r);

        return `
            <tr>
                <td class="text-start ps-4 fw-medium text-secondary">
                    <i class="bi bi-calendar3 me-1 text-muted small"></i>
                    ${escapeHtml(r.recorded_at || '--')}
                </td>
                <td>
                    <strong>${tempVal.toFixed(1)} °C</strong>
                    <span class="badge ${tempCat.badgeClass} ms-1">${tempCat.label}</span>
                </td>
                <td>
                    <strong>${humVal.toFixed(1)} %</strong>
                    <span class="badge ${humCat.badgeClass} ms-1">${humCat.label}</span>
                </td>
                <td>
                    <span class="badge ${rainStatus.isRain ? 'bg-primary' : 'bg-light text-dark border'}">
                        <i class="bi ${rainStatus.isRain ? 'bi-cloud-rain-fill' : 'bi-cloud'} me-1"></i>
                        ${rainStatus.label}
                    </span>
                </td>
                <td>
                    <code class="text-dark bg-light px-2 py-1 rounded border">${rainStatus.raw}</code>
                </td>
            </tr>
        `;
    }).join('');
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
