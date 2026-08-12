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

    function setupMobileNavigation() {
        const toggle = document.getElementById('navMenuToggle');
        const menu = document.getElementById('navMenu');
        if (!toggle || !menu) return;

        toggle.addEventListener('click', () => {
            const isOpen = menu.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', String(isOpen));
        });

        menu.addEventListener('click', (event) => {
            if (event.target.matches('.nav-link')) {
                menu.classList.remove('is-open');
                toggle.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            applyDarkMode();
            setupDarkModeToggle();
            setupMobileNavigation();
            console.log('Dark mode initialized:', isDarkMode());
        });
    } else {
        applyDarkMode();
        setupDarkModeToggle();
        setupMobileNavigation();
        console.log('Dark mode initialized (DOM ready):', isDarkMode());
    }

    // Make toggle function available globally
    window.toggleDarkMode = toggleDarkMode;
    window.isDarkMode = isDarkMode;
})();
