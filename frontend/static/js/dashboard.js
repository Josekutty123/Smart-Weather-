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
let lastProcessedReadingId = 0; // Guard against out-of-order older packets

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
 * Determine Rain status and category:
 * - NO RAIN: Badge 'NO RAIN' (bg-secondary)
 * - LIGHT RAIN: Badge 'LOW' (bg-primary)
 * - MEDIUM RAIN: Badge 'MEDIUM' (bg-success)
 * - HEAVY RAIN: Badge 'HIGH' (bg-danger)
 */
function getRainStatus(reading) {
    if (!reading) {
        return { label: '--', category: '--', badgeClass: 'bg-secondary text-white', isRain: false };
    }
    
    let isDetected = false;
    const rd = reading.rain_detected;
    if (rd === true || rd === 1 || rd === '1' || rd === 'true') {
        isDetected = true;
    } else if (reading.rain_status && typeof reading.rain_status === 'string') {
        const s = reading.rain_status.toLowerCase();
        if (s.includes('no water') || s.includes('no rain') || s.includes('no_rain') || s.includes('dry')) {
            isDetected = false;
        } else if (s.includes('water') || s.includes('rain') || s.includes('heavy') || s.includes('medium') || s.includes('light')) {
            isDetected = true;
        }
    } else if (reading.rain_value === 0) {
        isDetected = true;
    }
    
    if (!isDetected) {
        return {
            label: 'No Rain',
            category: 'NO RAIN',
            badgeClass: 'bg-secondary text-white',
            isRain: false
        };
    }

    const s = String(reading.rain_status || reading.rain_level || '').toLowerCase();
    const rawVal = parseFloat(reading.rain_value);

    // Explicit text check
    if (s.includes('heavy') || s.includes('high')) {
        return { label: 'Heavy Rain', category: 'HIGH', badgeClass: 'bg-danger text-white', isRain: true };
    }
    if (s.includes('medium') || s.includes('moderate')) {
        return { label: 'Medium Rain', category: 'MEDIUM', badgeClass: 'bg-success text-white', isRain: true };
    }
    if (s.includes('light') || s.includes('low')) {
        return { label: 'Light Rain', category: 'LOW', badgeClass: 'bg-primary text-white', isRain: true };
    }

    // Intensity percentage check if sent as analog (2-100% or ADC)
    if (!isNaN(rawVal) && rawVal > 1) {
        let percent = rawVal;
        if (rawVal > 100) percent = Math.max(0, Math.min(100, Math.round((4095 - rawVal) / 4095 * 100)));
        if (percent > 70) {
            return { label: 'Heavy Rain', category: 'HIGH', badgeClass: 'bg-danger text-white', isRain: true };
        } else if (percent >= 30) {
            return { label: 'Medium Rain', category: 'MEDIUM', badgeClass: 'bg-success text-white', isRain: true };
        } else {
            return { label: 'Light Rain', category: 'LOW', badgeClass: 'bg-primary text-white', isRain: true };
        }
    }

    // Default for digital active-LOW (water actively detected on plate)
    return {
        label: 'Heavy Rain',
        category: 'HIGH',
        badgeClass: 'bg-danger text-white',
        isRain: true
    };
}

// ============================================================
// 3. Main Initialization & Event Listeners
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    // Initial data fetches
    fetchLatestData();
    fetchHistoryData(currentChartRange);

    // Setup polling: Auto-refresh real-time cards every 4 seconds without manual reload
    setInterval(() => {
        fetchLatestData();
    }, 4000);

    // Setup polling: Charts and history logs every 8 seconds
    setInterval(() => {
        fetchHistoryData(currentChartRange);
    }, 8000);

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
        const isOnline = Boolean(data.device && data.device.is_online);
        const deviceId = data.device && data.device.device_id ? data.device.device_id : 'ESP32_FARM_01';
        if (sidebarNodeId) sidebarNodeId.innerText = deviceId;

        // Display offline warning banner if ESP32 stops transmitting
        const offlineNotice = document.getElementById('device-offline-notice');
        if (offlineNotice) {
            if (isOnline || !data.reading) {
                offlineNotice.classList.add('d-none');
            } else {
                offlineNotice.classList.remove('d-none');
            }
        }

        if (isOnline) {
            if (deviceStatusBadge) deviceStatusBadge.className = 'badge bg-success connection-badge d-flex align-items-center gap-1';
            if (deviceStatusText) deviceStatusText.innerText = 'ESP32 ONLINE';
            if (valDeviceState) {
                valDeviceState.innerText = 'ONLINE';
                valDeviceState.className = 'card-value mb-0 fs-3 text-success';
            }
            if (sidebarPulseDot) sidebarPulseDot.className = 'status-pulse-dot online';
            if (sidebarNodeStatus) sidebarNodeStatus.innerText = 'Connected & Active';
        } else {
            if (deviceStatusBadge) deviceStatusBadge.className = 'badge bg-secondary connection-badge d-flex align-items-center gap-1';
            if (deviceStatusText) deviceStatusText.innerText = 'ESP32 OFFLINE';
            if (valDeviceState) {
                valDeviceState.innerText = 'OFFLINE';
                valDeviceState.className = 'card-value mb-0 fs-3 text-secondary';
            }
            if (sidebarPulseDot) sidebarPulseDot.className = 'status-pulse-dot';
            if (sidebarNodeStatus) sidebarNodeStatus.innerText = 'Disconnected';
        }

        // 2. Sensor Readings Update
        const reading = data.reading;
        if (reading) {
            // Out-of-order packet protection: Older readings must not overwrite newer readings
            if (reading.id && reading.id < lastProcessedReadingId) {
                console.warn(`Skipping older packet id #${reading.id} (Current: #${lastProcessedReadingId})`);
                return;
            }
            if (reading.id) {
                lastProcessedReadingId = reading.id;
            }

            if (noDataNotice) noDataNotice.classList.add('d-none');

            // Format timestamp
            const recordedAt = reading.recorded_at || 'Just now';
            const timePart = recordedAt.split(' ').length > 1 ? recordedAt.split(' ')[1] : recordedAt;
            if (valLastSeenHeader) valLastSeenHeader.innerText = `Sync: ${timePart}`;
            if (valLastSeenCard) valLastSeenCard.innerText = `Last data: ${recordedAt}`;

            // 1. Temperature in °C & Category (LOW, MEDIUM, HIGH)
            const tempVal = parseFloat(reading.temperature);
            const valTemp = document.getElementById('val-temperature');
            if (valTemp) valTemp.innerText = `${tempVal.toFixed(1)} °C`;
            const tempCat = getTemperatureCategory(tempVal);
            const badgeTemp = document.getElementById('badge-temp-category');
            if (badgeTemp) {
                badgeTemp.innerText = tempCat.label;
                badgeTemp.className = `badge ${tempCat.badgeClass} category-badge`;
            }

            // 2. Humidity in % & Category (LOW, MEDIUM, HIGH)
            const humVal = parseFloat(reading.humidity);
            const valHum = document.getElementById('val-humidity');
            if (valHum) valHum.innerText = `${humVal.toFixed(1)} %`;
            const humCat = getHumidityCategory(humVal);
            const badgeHum = document.getElementById('badge-hum-category');
            if (badgeHum) {
                badgeHum.innerText = humCat.label;
                badgeHum.className = `badge ${humCat.badgeClass} category-badge`;
            }

            // 3. Rain Status (NO RAIN / LIGHT RAIN / MEDIUM RAIN / HEAVY RAIN)
            const rainStatus = getRainStatus(reading);
            const valRainStatus = document.getElementById('val-rain-status');
            const badgeRain = document.getElementById('badge-rain-category');
            const rainIcon = document.getElementById('rain-card-icon');
            const rainIconBox = document.getElementById('rain-icon-box');
            const cardRain = document.getElementById('card-rain');
            const rainConditionLabel = document.getElementById('rain-condition-label');

            if (valRainStatus) {
                valRainStatus.innerText = rainStatus.label;
                valRainStatus.className = `card-value mb-0 fw-bold ${rainStatus.isRain ? 'text-primary' : 'text-dark'}`;
            }
            if (badgeRain) {
                badgeRain.innerText = rainStatus.category;
                badgeRain.className = `badge ${rainStatus.badgeClass} category-badge`;
            }
            if (rainIcon) {
                if (!rainStatus.isRain) {
                    rainIcon.className = 'bi bi-cloud-sun text-secondary';
                } else if (rainStatus.category === 'HIGH') {
                    rainIcon.className = 'bi bi-cloud-rain-heavy-fill text-danger';
                } else if (rainStatus.category === 'MEDIUM') {
                    rainIcon.className = 'bi bi-cloud-rain text-success';
                } else {
                    rainIcon.className = 'bi bi-cloud-drizzle text-primary';
                }
            }
            if (rainIconBox) {
                rainIconBox.style.backgroundColor = rainStatus.isRain ? '#cff4fc' : '#e0f7fa';
            }
            if (cardRain) {
                if (rainStatus.isRain) {
                    cardRain.className = `card summary-card border ${rainStatus.category === 'HIGH' ? 'border-danger' : 'border-primary'} border-2 shadow h-100`;
                } else {
                    cardRain.className = 'card summary-card border-0 shadow-sm h-100';
                }
            }
            if (rainConditionLabel) {
                rainConditionLabel.innerHTML = rainStatus.isRain ? 
                    `<i class="bi bi-droplet-fill text-primary me-1"></i>${rainStatus.label}` : 
                    '<i class="bi bi-shield-check text-success me-1"></i>Plate Dry';
            }

            // 4. Update Farmer Alerts
            updateFarmerAlerts(tempVal, humVal, rainStatus.isRain);

        } else {
            // No telemetry yet
            if (noDataNotice) noDataNotice.classList.remove('d-none');
            const valTemp = document.getElementById('val-temperature');
            const valHum = document.getElementById('val-humidity');
            const valRain = document.getElementById('val-rain-status');
            if (valTemp) valTemp.innerText = '-- °C';
            if (valHum) valHum.innerText = '-- %';
            if (valRain) valRain.innerText = 'No Water Detected';
            if (valLastSeenHeader) valLastSeenHeader.innerText = 'Sync: Waiting...';
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

    // 3. Rain / Water Detected Alert
    if (isRain) {
        activeAlerts.push({
            type: 'info',
            icon: 'bi-cloud-rain-fill text-primary',
            title: 'Water Alert',
            message: 'Water detected on the field sensor plate. Pause active irrigation channels.'
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
        tableBody.innerHTML = '<tr><td colspan="4" class="text-muted py-4">Waiting for sensor data from ESP32...</td></tr>';
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
                    <strong class="fs-6">${tempVal.toFixed(1)} °C</strong>
                    <span class="badge ${tempCat.badgeClass} ms-1">${tempCat.label}</span>
                </td>
                <td>
                    <strong class="fs-6">${humVal.toFixed(1)} %</strong>
                    <span class="badge ${humCat.badgeClass} ms-1">${humCat.label}</span>
                </td>
                <td>
                    <span class="badge ${rainStatus.badgeClass} px-3 py-2">
                        <i class="bi ${rainStatus.isRain ? (rainStatus.category === 'HIGH' ? 'bi-cloud-rain-heavy-fill' : 'bi-cloud-rain') : 'bi-cloud-sun'} me-1"></i>
                        ${rainStatus.label} (${rainStatus.category})
                    </span>
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
