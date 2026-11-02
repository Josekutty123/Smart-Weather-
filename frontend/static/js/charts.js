/**
 * Smart Weather Monitoring System - Interactive Charts (Chart.js)
 * Visualizes real telemetry from MySQL database:
 * 1. Temperature History (°C)
 * 2. Humidity History (%)
 * 3. Rain Monitoring History (Rain Detected vs No Rain periods)
 */

let tempChartInstance = null;
let humChartInstance = null;
let rainChartInstance = null;

function initCharts() {
    const tempCanvas = document.getElementById('tempChart');
    const humCanvas = document.getElementById('humChart');
    const rainCanvas = document.getElementById('rainChart');

    if (!tempCanvas || !humCanvas || !rainCanvas) return;

    // Common Tooltip & Grid Config
    const commonPlugins = {
        legend: { display: false },
        tooltip: {
            backgroundColor: 'rgba(18, 55, 42, 0.9)',
            padding: 10,
            cornerRadius: 8,
            titleFont: { size: 12, weight: '600' },
            bodyFont: { size: 12 }
        }
    };

    // 1. Temperature History Chart
    tempChartInstance = new Chart(tempCanvas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature (°C)',
                data: [],
                borderColor: '#e11d48',
                backgroundColor: 'rgba(225, 29, 72, 0.1)',
                fill: true,
                tension: 0.35,
                borderWidth: 2.5,
                pointRadius: 2.5,
                pointHoverRadius: 6,
                pointBackgroundColor: '#e11d48'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                ...commonPlugins,
                tooltip: {
                    ...commonPlugins.tooltip,
                    callbacks: {
                        label: (ctx) => ` Temperature: ${ctx.parsed.y.toFixed(1)} °C`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 10 }, color: '#64748b' }
                },
                y: {
                    title: { display: true, text: 'Temperature (°C)', font: { size: 11, weight: '600' }, color: '#64748b' },
                    grid: { color: 'rgba(0, 0, 0, 0.05)' },
                    ticks: { font: { size: 10 }, color: '#64748b' }
                }
            }
        }
    });

    // 2. Humidity History Chart
    humChartInstance = new Chart(humCanvas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Humidity (%)',
                data: [],
                borderColor: '#0284c7',
                backgroundColor: 'rgba(2, 132, 199, 0.1)',
                fill: true,
                tension: 0.35,
                borderWidth: 2.5,
                pointRadius: 2.5,
                pointHoverRadius: 6,
                pointBackgroundColor: '#0284c7'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                ...commonPlugins,
                tooltip: {
                    ...commonPlugins.tooltip,
                    callbacks: {
                        label: (ctx) => ` Humidity: ${ctx.parsed.y.toFixed(1)} %`
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 10 }, color: '#64748b' }
                },
                y: {
                    min: 0,
                    max: 100,
                    title: { display: true, text: 'Humidity (%)', font: { size: 11, weight: '600' }, color: '#64748b' },
                    grid: { color: 'rgba(0, 0, 0, 0.05)' },
                    ticks: { font: { size: 10 }, color: '#64748b' }
                }
            }
        }
    });

    // 3. Rain Monitoring History (Actual Rain Detection Timeline)
    rainChartInstance = new Chart(rainCanvas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Rain Detection',
                data: [],
                stepped: true, // Binary step chart: 1 = Rain Detected, 0 = No Rain
                borderColor: '#0891b2',
                backgroundColor: 'rgba(8, 145, 178, 0.18)',
                fill: true,
                borderWidth: 2,
                pointRadius: 2,
                pointHoverRadius: 5,
                pointBackgroundColor: '#0891b2'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                ...commonPlugins,
                tooltip: {
                    ...commonPlugins.tooltip,
                    callbacks: {
                        label: (ctx) => {
                            const isRain = ctx.parsed.y === 1;
                            const raw = ctx.raw && ctx.raw.rawValue !== undefined ? ` (Raw ADC: ${ctx.raw.rawValue})` : '';
                            return ` Status: ${isRain ? 'RAIN DETECTED' : 'NO RAIN'}${raw}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45, font: { size: 10 }, color: '#64748b' }
                },
                y: {
                    min: 0,
                    max: 1,
                    ticks: {
                        stepSize: 1,
                        callback: (val) => val === 1 ? 'RAIN DETECTED' : 'NO RAIN',
                        font: { size: 10, weight: '600' },
                        color: (ctx) => ctx.tick.value === 1 ? '#0891b2' : '#64748b'
                    },
                    grid: { color: 'rgba(0, 0, 0, 0.05)' }
                }
            }
        }
    });
}

/**
 * Format timestamps for X-axis labels
 */
function formatChartLabel(recordedAt) {
    if (!recordedAt) return '';
    // Format "YYYY-MM-DD HH:MM:SS" -> "HH:MM:SS" or "MM-DD HH:MM"
    const parts = recordedAt.split(' ');
    if (parts.length > 1) {
        return parts[1].substring(0, 8);
    }
    return recordedAt;
}

/**
 * Update all three Chart.js charts with real database readings
 */
function updateAllCharts(readings) {
    if (!tempChartInstance || !humChartInstance || !rainChartInstance) return;

    const count = readings ? readings.length : 0;
    
    // Update badge indicators
    const tempCountBadge = document.getElementById('temp-chart-count');
    const humCountBadge = document.getElementById('hum-chart-count');
    const rainCountBadge = document.getElementById('rain-chart-count');
    if (tempCountBadge) tempCountBadge.innerText = `${count} pts`;
    if (humCountBadge) humCountBadge.innerText = `${count} pts`;
    if (rainCountBadge) rainCountBadge.innerText = `${count} pts`;

    if (!readings || readings.length === 0) {
        tempChartInstance.data.labels = [];
        tempChartInstance.data.datasets[0].data = [];
        tempChartInstance.update();

        humChartInstance.data.labels = [];
        humChartInstance.data.datasets[0].data = [];
        humChartInstance.update();

        rainChartInstance.data.labels = [];
        rainChartInstance.data.datasets[0].data = [];
        rainChartInstance.update();
        return;
    }

    const labels = readings.map(r => formatChartLabel(r.recorded_at));
    const temps = readings.map(r => parseFloat(r.temperature));
    const hums = readings.map(r => parseFloat(r.humidity));
    
    // Binary rain detection: 1 for rain detected, 0 for dry
    const rainData = readings.map(r => ({
        x: formatChartLabel(r.recorded_at),
        y: r.rain_detected ? 1 : 0,
        rawValue: r.rain_value !== undefined ? r.rain_value : '--'
    }));

    // Update Temperature Chart
    tempChartInstance.data.labels = labels;
    tempChartInstance.data.datasets[0].data = temps;
    tempChartInstance.update('none'); // Smooth transition without flash

    // Update Humidity Chart
    humChartInstance.data.labels = labels;
    humChartInstance.data.datasets[0].data = hums;
    humChartInstance.update('none');

    // Update Rain Chart
    rainChartInstance.data.labels = labels;
    rainChartInstance.data.datasets[0].data = rainData;
    rainChartInstance.update('none');
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
});
