// MCPDaily Dashboard JavaScript
// Modern dashboard with dark mode support

// Configuration
const API_BASE_URL = window.location.origin;
const API_ENDPOINT = `${API_BASE_URL}/invoke`;
const AUTO_REFRESH_INTERVAL = 5 * 60 * 1000; // 5 minutes

// State management
let autoRefreshEnabled = true;
let autoRefreshTimer = null;
let currentTimezone = 'UTC';
let currentLocation = 'London';
let currentNewsCategory = 'technology';
let currentNewsLimit = 5;

// Theme Management
function initTheme() {
    const savedTheme = localStorage.getItem('mcpdaily-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('mcpdaily-theme', newTheme);
}

// API Call Utility
async function invokeToolAPI(toolName, payload = {}) {
    const requestId = Date.now().toString();

    try {
        const response = await fetch(API_ENDPOINT, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                id: requestId,
                tool: toolName,
                payload: payload
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        if (data.status === 'error') {
            throw new Error(data.error || 'Unknown error occurred');
        }

        return data.result;
    } catch (error) {
        console.error(`Error invoking ${toolName}:`, error);
        throw error;
    }
}

// UI State Management
function showLoading(tool) {
    const loading = document.getElementById(`${tool}Loading`);
    const error = document.getElementById(`${tool}Error`);
    const content = document.getElementById(`${tool}Content`);

    if (loading) loading.classList.add('show');
    if (error) error.classList.remove('show');
    if (content) content.classList.remove('show');
}

function hideLoading(tool) {
    const loading = document.getElementById(`${tool}Loading`);
    if (loading) loading.classList.remove('show');
}

function showError(tool, message) {
    hideLoading(tool);
    const error = document.getElementById(`${tool}Error`);
    const content = document.getElementById(`${tool}Content`);

    if (error) {
        error.textContent = message;
        error.classList.add('show');
    }
    if (content) content.classList.remove('show');
}

function showContent(tool) {
    hideLoading(tool);
    const error = document.getElementById(`${tool}Error`);
    const content = document.getElementById(`${tool}Content`);

    if (error) error.classList.remove('show');
    if (content) content.classList.add('show');
}

function updateLastUpdateTime() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    const lastUpdateElement = document.getElementById('lastUpdate');
    if (lastUpdateElement) {
        lastUpdateElement.textContent = timeString;
    }
}

// Time Tool Functions
async function fetchTimeData(timezone = 'UTC') {
    showLoading('time');

    try {
        const result = await invokeToolAPI('timetool', { timezone });
        displayTimeData(result);
        showContent('time');
    } catch (error) {
        showError('time', `Failed to fetch time data: ${error.message}`);
    }
}

function displayTimeData(data) {
    // Update time display
    const timeParts = data.time_12hr.split(' ');
    const time = timeParts[0];

    document.getElementById('currentTime').textContent = time;

    // Update date display
    const dateStr = `${data.day_of_week}, ${data.date}`;
    document.getElementById('dateDisplay').textContent = dateStr;

    // Update timezone info
    document.getElementById('timezoneName').textContent = data.timezone;
    document.getElementById('timezoneAbbr').textContent = ` (${data.timezone_abbr})`;

    // Update UTC time
    const utcTimeParts = data.utc_time.split(' ');
    document.getElementById('utcTime').textContent = utcTimeParts[1];
}

// Weather Tool Functions
async function fetchWeatherData(location) {
    showLoading('weather');

    try {
        const result = await invokeToolAPI('weathertool', { location });
        displayWeatherData(result);
        showContent('weather');

        // Show cache indicator
        const cacheEl = document.getElementById('weatherCache');
        if (cacheEl) {
            if (result.cached) {
                cacheEl.classList.add('show');
            } else {
                cacheEl.classList.remove('show');
            }
        }
    } catch (error) {
        showError('weather', `Failed to fetch weather data: ${error.message}`);
    }
}

function displayWeatherData(data) {
    // Location and temperature
    document.getElementById('locationName').textContent = data.location;
    document.getElementById('temperature').textContent = Math.round(data.temperature.current);
    document.getElementById('feelsLike').textContent = Math.round(data.temperature.feels_like);

    // Conditions
    document.getElementById('conditions').textContent = data.conditions.description;

    // Temperature range
    document.getElementById('tempMin').textContent = Math.round(data.temperature.min);
    document.getElementById('tempMax').textContent = Math.round(data.temperature.max);

    // Details
    document.getElementById('humidity').textContent = data.humidity;
    document.getElementById('pressure').textContent = data.pressure;
    document.getElementById('windSpeed').textContent = data.wind.speed.toFixed(1);
}

// News Tool Functions
async function fetchNewsData(category, limit) {
    showLoading('news');

    try {
        const result = await invokeToolAPI('newstool', {
            category,
            limit: parseInt(limit)
        });
        displayNewsData(result);
        showContent('news');

        // Show cache indicator
        const cacheEl = document.getElementById('newsCache');
        if (cacheEl) {
            if (result.cached) {
                cacheEl.classList.add('show');
            } else {
                cacheEl.classList.remove('show');
            }
        }
    } catch (error) {
        showError('news', `Failed to fetch news data: ${error.message}`);
    }
}

function displayNewsData(data) {
    const newsListElement = document.getElementById('newsList');

    if (!data.headlines || data.headlines.length === 0) {
        newsListElement.innerHTML = '<p style="text-align: center; color: var(--text-tertiary); padding: 40px;">No news headlines available.</p>';
        return;
    }

    newsListElement.innerHTML = data.headlines.map(article => {
        const publishedDate = new Date(article.published_at);
        const formattedDate = publishedDate.toLocaleDateString();
        const formattedTime = publishedDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        return `
            <div class="news-item">
                <div class="news-item-header">
                    <h3 class="news-title">
                        <a href="${article.url}" target="_blank" rel="noopener noreferrer">
                            ${escapeHtml(article.title)}
                        </a>
                    </h3>
                    <span class="news-source">${escapeHtml(article.source)}</span>
                </div>
                <div class="news-meta">
                    ${article.author ? `<span>By ${escapeHtml(article.author)}</span>` : ''}
                    <span>${formattedDate} ${formattedTime}</span>
                </div>
                ${article.description ? `<p class="news-description">${escapeHtml(article.description)}</p>` : ''}
            </div>
        `;
    }).join('');
}

// Utility function to escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Refresh all data
async function refreshAllData() {
    updateLastUpdateTime();
    await Promise.all([
        fetchTimeData(currentTimezone),
        fetchWeatherData(currentLocation),
        fetchNewsData(currentNewsCategory, currentNewsLimit)
    ]);
}

// Auto-refresh management
function startAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }

    if (autoRefreshEnabled) {
        autoRefreshTimer = setInterval(() => {
            console.log('Auto-refreshing data...');
            refreshAllData();
        }, AUTO_REFRESH_INTERVAL);
    }
}

function stopAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        autoRefreshTimer = null;
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', function() {
    console.log('MCPDaily Dashboard loaded');

    // Initialize theme
    initTheme();

    // Set initial values
    document.getElementById('timezoneSelect').value = currentTimezone;
    document.getElementById('locationInput').value = currentLocation;
    document.getElementById('newsCategory').value = currentNewsCategory;
    document.getElementById('newsLimit').value = currentNewsLimit;
    document.getElementById('autoRefresh').checked = autoRefreshEnabled;

    // Theme Toggle
    document.getElementById('themeToggle').addEventListener('click', toggleTheme);

    // Refresh All button
    document.getElementById('refreshAll').addEventListener('click', function() {
        console.log('Manual refresh triggered');
        refreshAllData();
    });

    // Auto-refresh toggle
    document.getElementById('autoRefresh').addEventListener('change', function(e) {
        autoRefreshEnabled = e.target.checked;
        if (autoRefreshEnabled) {
            console.log('Auto-refresh enabled');
            startAutoRefresh();
        } else {
            console.log('Auto-refresh disabled');
            stopAutoRefresh();
        }
    });

    // Individual refresh buttons
    document.querySelectorAll('.refresh-btn').forEach(button => {
        button.addEventListener('click', function() {
            const tool = this.getAttribute('data-tool');
            console.log(`Refreshing ${tool} tool`);

            switch(tool) {
                case 'time':
                    fetchTimeData(currentTimezone);
                    break;
                case 'weather':
                    fetchWeatherData(currentLocation);
                    break;
                case 'news':
                    fetchNewsData(currentNewsCategory, currentNewsLimit);
                    break;
            }
        });
    });

    // Timezone selector
    document.getElementById('timezoneSelect').addEventListener('change', function(e) {
        currentTimezone = e.target.value;
        console.log(`Timezone changed to: ${currentTimezone}`);
        fetchTimeData(currentTimezone);
    });

    // Location update button
    document.getElementById('updateLocation').addEventListener('click', function() {
        const locationInput = document.getElementById('locationInput');
        const newLocation = locationInput.value.trim();

        if (newLocation) {
            currentLocation = newLocation;
            console.log(`Location changed to: ${currentLocation}`);
            fetchWeatherData(currentLocation);
        }
    });

    // Location input - Enter key support
    document.getElementById('locationInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            document.getElementById('updateLocation').click();
        }
    });

    // News category selector
    document.getElementById('newsCategory').addEventListener('change', function(e) {
        currentNewsCategory = e.target.value;
        console.log(`News category changed to: ${currentNewsCategory}`);
        fetchNewsData(currentNewsCategory, currentNewsLimit);
    });

    // News limit selector
    document.getElementById('newsLimit').addEventListener('change', function(e) {
        currentNewsLimit = e.target.value;
        console.log(`News limit changed to: ${currentNewsLimit}`);
        fetchNewsData(currentNewsCategory, currentNewsLimit);
    });

    // Initial data load
    console.log('Loading initial data...');
    refreshAllData();

    // Start auto-refresh if enabled
    if (autoRefreshEnabled) {
        startAutoRefresh();
    }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    stopAutoRefresh();
});
