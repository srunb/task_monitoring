// Common JavaScript functions for all pages

(function() {
    // Dark mode state
    const STORAGE_KEY = 'darkMode';

    function isDarkMode() {
        return localStorage.getItem(STORAGE_KEY) === 'true';
    }

    function setDarkMode(enabled) {
        localStorage.setItem(STORAGE_KEY, enabled ? 'true' : 'false');
    }

    function applyDarkMode() {
        if (isDarkMode()) {
            document.documentElement.classList.add('dark-mode');
        } else {
            document.documentElement.classList.remove('dark-mode');
        }
        updateDarkModeIcon();
    }

    function updateDarkModeIcon() {
        const icon = document.getElementById('darkModeIcon');
        if (icon) {
            icon.textContent = isDarkMode() ? '☀️' : '🌙';
        }
    }

    function toggleDarkMode() {
        const newValue = !isDarkMode();
        setDarkMode(newValue);
        applyDarkMode();
        console.log('Dark mode toggled:', newValue);
    }

    function setupDarkModeToggle() {
        const toggle = document.getElementById('darkModeToggle');
        if (toggle) {
            console.log('Setting up dark mode toggle');
            toggle.addEventListener('click', toggleDarkMode);
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            applyDarkMode();
            setupDarkModeToggle();
            console.log('Dark mode initialized:', isDarkMode());
        });
    } else {
        applyDarkMode();
        setupDarkModeToggle();
        console.log('Dark mode initialized (DOM ready):', isDarkMode());
    }

    // Make toggle function available globally
    window.toggleDarkMode = toggleDarkMode;
    window.isDarkMode = isDarkMode;
})();
