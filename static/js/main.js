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
    // Mobile Sidebar Toggle
    const toggle = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const navLinks = document.querySelectorAll('.nav-links a');

    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('active');
            overlay.style.display = sidebar.classList.contains('active') ? 'block' : 'none';
        });

        overlay.addEventListener('click', () => {
            sidebar.classList.remove('active');
            overlay.style.display = 'none';
        });

        // Close sidebar when a link is clicked on mobile
        navLinks.forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 992) {
                    sidebar.classList.remove('active');
                    overlay.style.display = 'none';
                }
            });
        });
    }
});
