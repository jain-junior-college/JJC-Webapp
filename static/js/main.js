// Main Interactivity for JJ-CMS
document.addEventListener('DOMContentLoaded', () => {
    console.log('JJ-CMS UI Initialized');
    
    // Auto-dismiss flash messages after 5 seconds
    const alerts = document.querySelectorAll('.animate-in');
    alerts.forEach(alert => {
        if (alert.style.color === '#065f46') { // Success messages
            setTimeout(() => {
                alert.style.opacity = '0';
                alert.style.transition = 'opacity 0.5s ease';
                setTimeout(() => alert.remove(), 500);
            }, 5000);
        }
    });
});
