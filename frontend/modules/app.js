import { isLoggedIn } from './api/client.js?v=3';

const V = '?v=3';
const routes = {
    '/login': () => import('./pages/login.js' + V),
    '/platform': () => import('./pages/platform.js' + V),
    '/backtest': () => import('./pages/backtest.js' + V),
    '/data': () => import('./pages/data.js' + V),
    '/ops': () => import('./pages/ops.js' + V),
};

const PUBLIC_ROUTES = ['/login'];
let currentModule = null;

async function navigate(path) {
    // Auth check
    if (!PUBLIC_ROUTES.includes(path) && !isLoggedIn()) {
        window.location.hash = '#/login';
        return;
    }
    if (path === '/login' && isLoggedIn()) {
        window.location.hash = '#/platform';
        return;
    }

    const container = document.getElementById('app');
    if (currentModule?.destroy) currentModule.destroy();

    // Show/hide nav for login page
    document.getElementById('nav').style.display = path === '/login' ? 'none' : 'flex';

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
