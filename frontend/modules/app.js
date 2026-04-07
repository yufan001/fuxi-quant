const V = '?v=2';
const routes = {
    '/platform': () => import('./pages/platform.js' + V),
    '/backtest': () => import('./pages/backtest.js' + V),
    '/data': () => import('./pages/data.js' + V),
    '/ops': () => import('./pages/ops.js' + V),
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
