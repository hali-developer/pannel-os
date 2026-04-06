/**
 * VPS Panel — Frontend JavaScript
 * Toast notifications, sidebar toggle, confirmations
 */

// ═══════════════════════════════════════
// SIDEBAR TOGGLE (Mobile)
// ═══════════════════════════════════════
document.addEventListener('DOMContentLoaded', function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggleBtn = document.getElementById('sidebarToggle');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('show');
            if (overlay) overlay.classList.toggle('show');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
        });
    }

    // ── Active Navigation Highlight ──
    highlightActiveNav();

    // ── Flash Messages → Toasts ──
    processFlashMessages();

    // ── Delete Confirmation ──
    bindDeleteConfirmations();
});


// ═══════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════
function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const iconMap = {
        success: 'bi-check-circle-fill',
        danger: 'bi-exclamation-triangle-fill',
        warning: 'bi-exclamation-circle-fill',
        info: 'bi-info-circle-fill',
    };

    const toast = document.createElement('div');
    toast.className = `panel-toast ${type}`;
    toast.innerHTML = `
        <i class="bi ${iconMap[type] || iconMap.info} toast-icon"></i>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;

    container.appendChild(toast);

    // Auto remove after 5 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-in forwards';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}


// ═══════════════════════════════════════
// FLASH MESSAGES → TOASTS
// ═══════════════════════════════════════
function processFlashMessages() {
    const flashContainer = document.getElementById('flashMessages');
    if (!flashContainer) return;

    const messages = flashContainer.querySelectorAll('[data-flash]');
    messages.forEach(function (el) {
        const type = el.dataset.type || 'info';
        const message = el.dataset.flash;
        if (message) {
            showToast(message, type);
        }
    });

    flashContainer.remove();
}


// ═══════════════════════════════════════
// ACTIVE NAVIGATION
// ═══════════════════════════════════════
function highlightActiveNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.sidebar-nav .nav-link');

    navLinks.forEach(function (link) {
        const href = link.getAttribute('href');
        link.classList.remove('active');

        if (href === currentPath) {
            link.classList.add('active');
        } else if (href !== '/' && currentPath.startsWith(href)) {
            link.classList.add('active');
        }
    });
}


// ═══════════════════════════════════════
// DELETE CONFIRMATION
// ═══════════════════════════════════════
function bindDeleteConfirmations() {
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            const message = this.dataset.confirm || 'Are you sure you want to proceed?';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
}


// ═══════════════════════════════════════
// FORM HELPERS
// ═══════════════════════════════════════
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function () {
        showToast('Copied to clipboard!', 'success');
    }).catch(function () {
        showToast('Failed to copy.', 'danger');
    });
}
