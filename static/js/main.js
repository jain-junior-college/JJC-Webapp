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

// Global PDF Download Utility
function downloadPDF(elementId, filename) {
    const element = document.getElementById(elementId);
    if (!element) {
        console.error("PDF download failed: Element not found - " + elementId);
        return;
    }
    
    // Configure html2pdf
    const opt = {
        margin:       [0.5, 0.5, 0.5, 0.5], // top, left, bottom, right in inches
        filename:     filename || 'Report.pdf',
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, useCORS: true, logging: false },
        jsPDF:        { unit: 'in', format: 'a4', orientation: 'portrait' }
    };
    
    // Add loading state to button if clicked from an event
    const btn = event && event.target ? event.target.closest('button') : null;
    let originalText = '';
    if (btn) {
        originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
        btn.disabled = true;
    }

    html2pdf().set(opt).from(element).save().then(() => {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }).catch(err => {
        console.error("PDF Generation Error:", err);
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
        alert("An error occurred while generating the PDF.");
    });
}
