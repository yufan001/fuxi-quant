const routes = {
    '/platform': () => import('./pages/platform.js'),
    '/backtest': () => import('./pages/backtest.js'),
    '/data': () => import('./pages/data.js'),
    '/ops': () => import('./pages/ops.js'),
};

let currentModule = null;

async function navigate(path) {
    const container = document.getElementById('app');
    if (currentModule?.destroy) currentModule.destroy();

    const loader = routes[path];
    if (!loader) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">页面不存在</div>';
        return;
    }

    currentModule = await loader();
    await currentModule.render(container);

    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('href') === '#' + path);
    });
}

function getPath() {
    return window.location.hash.slice(1) || '/platform';
}

window.addEventListener('hashchange', () => navigate(getPath()));
window.addEventListener('DOMContentLoaded', () => navigate(getPath()));
