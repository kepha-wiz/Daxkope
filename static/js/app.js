// Cash Flow Future AI — vanilla JS helpers
document.addEventListener('DOMContentLoaded', () => {
    // Auto-dismiss flash messages
    document.querySelectorAll('.flash').forEach(flash => {
        setTimeout(() => {
            flash.style.transition = 'opacity .4s, transform .4s';
            flash.style.opacity = '0';
            flash.style.transform = 'translateX(100%)';
            setTimeout(() => flash.remove(), 400);
        }, 4500);
    });

    // Copy referral URL
    document.querySelectorAll('[data-copy]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const text = btn.dataset.copy;
            try {
                await navigator.clipboard.writeText(text);
                const original = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => btn.textContent = original, 1500);
            } catch (e) {
                alert('Copy failed. Please copy manually: ' + text);
            }
        });
    });

    // Confirm dangerous actions
    document.querySelectorAll('[data-confirm]').forEach(el => {
        el.addEventListener('click', (e) => {
            if (!confirm(el.dataset.confirm)) e.preventDefault();
        });
    });

    // Mobile bottom nav active state
    const path = window.location.pathname;
    document.querySelectorAll('.bottom-nav-list a').forEach(a => {
        if (a.getAttribute('href') === path) a.classList.add('active');
    });
    document.querySelectorAll('.nav-list a').forEach(a => {
        if (a.getAttribute('href') === path) a.classList.add('active');
    });

    // Animate progress bars on load
    document.querySelectorAll('.progress-bar').forEach(bar => {
        const target = bar.dataset.target || bar.style.width;
        bar.style.width = '0';
        requestAnimationFrame(() => {
            bar.style.transition = 'width 1.2s cubic-bezier(.2,.8,.2,1)';
            bar.style.width = target;
        });
    });

    // Simple tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const group = tab.dataset.tabGroup;
            const target = tab.dataset.tabTarget;
            document.querySelectorAll(`.tab[data-tab-group="${group}"]`).forEach(t => t.classList.remove('active'));
            document.querySelectorAll(`[data-tab-panel="${group}"]`).forEach(p => p.style.display = 'none');
            tab.classList.add('active');
            const panel = document.querySelector(`[data-tab-panel="${group}"][data-panel-id="${target}"]`);
            if (panel) panel.style.display = '';
        });
    });
});
