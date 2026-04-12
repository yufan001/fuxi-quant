const V = '?v=3';
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

    document.getElementById('nav').style.display = 'flex';

    const loader = routes[path] || routes['/platform'];
    currentModule = await loader();
    await currentModule.render(container);

    document.querySelectorAll('.nav-link').forEach(link => {
        const activePath = routes[path] ? path : '/platform';
        link.classList.toggle('active', link.getAttribute('href') === '#' + activePath);
    });
}

function getPath() {
    const path = window.location.hash.slice(1) || '/platform';
    return routes[path] ? path : '/platform';
}

window.addEventListener('hashchange', () => navigate(getPath()));
window.addEventListener('DOMContentLoaded', () => navigate(getPath()));
