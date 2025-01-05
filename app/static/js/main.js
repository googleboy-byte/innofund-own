// Toast notification system
function showToast(message, type = 'success') {
    // Remove existing toasts
    const existingToast = document.querySelector('.toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    // Add toast to document
    document.body.appendChild(toast);

    // Show toast with animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);

    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3000);
}

// Add toast styles to document
const style = document.createElement('style');
style.textContent = `
.toast {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: var(--dark-bg);
    color: var(--text-primary);
    padding: 12px 24px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    z-index: 1000;
    opacity: 0;
    transition: all 0.3s ease;
}

.toast.show {
    transform: translateX(-50%) translateY(0);
    opacity: 1;
}

.toast.toast-success {
    border-left: 4px solid var(--neon-green);
}

.toast.toast-error {
    border-left: 4px solid #ef4444;
}
`;
document.head.appendChild(style);

// Common utility functions
function copyToClipboard(text) {
    return navigator.clipboard.writeText(text)
        .then(() => {
            showToast('Copied to clipboard!');
        })
        .catch(err => {
            console.error('Failed to copy:', err);
            showToast('Failed to copy to clipboard', 'error');
        });
}

// Handle mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const menuToggle = document.querySelector('.mobile-menu-toggle');
    const mobileMenu = document.querySelector('.mobile-menu');
    
    if (menuToggle && mobileMenu) {
        menuToggle.addEventListener('click', () => {
            mobileMenu.classList.toggle('show');
        });
    }
}); 