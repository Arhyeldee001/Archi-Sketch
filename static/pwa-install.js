// static/js/pwa-install.js
let deferredPrompt;

function initPWAInstall() {
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        
        const installBtn = document.getElementById('install-btn');
        if (installBtn) {
            installBtn.style.display = 'block';
            installBtn.addEventListener('click', installPWA);
        }
    });
}

async function installPWA() {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        if (outcome === 'accepted') {
            console.log('PWA installed');
            const installBtn = document.getElementById('install-btn');
            if (installBtn) installBtn.style.display = 'none';
        }
        deferredPrompt = null;
    }
}

// Initialize when loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPWAInstall);
} else {
    initPWAInstall();
}