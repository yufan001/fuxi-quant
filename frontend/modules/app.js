const V = '?v=18';
const THEME_STORAGE_KEY = 'fuxi_xau_theme';
const routes = {
    '/xau': () => import('./pages/xau.js' + V),
};

let currentModule = null;

try {
    document.body.classList.toggle('theme-light', localStorage.getItem(THEME_STORAGE_KEY) === 'light');
} catch (e) {
    document.body.classList.remove('theme-light');
}

async function navigate(path) {
    const container = document.getElementById('app');
    if (currentModule?.destroy) currentModule.destroy();

    const activePath = routes[path] ? path : '/xau';
    document.body.classList.toggle('route-xau', activePath === '/xau');
    document.getElementById('nav').style.display = 'flex';

    const loader = routes[activePath];
    currentModule = await loader();
    await currentModule.render(container);

    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.getAttribute('href') === '#' + activePath);
    });
}

function getPath() {
    const path = window.location.hash.slice(1) || '/xau';
    return routes[path] ? path : '/xau';
}

window.addEventListener('hashchange', () => navigate(getPath()));
window.addEventListener('DOMContentLoaded', () => navigate(getPath()));
