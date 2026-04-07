import { login, setToken } from '../api/client.js';

export async function render(container) {
    container.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;height:100%;min-height:calc(100vh - 80px);">
            <div class="card" style="width:360px;padding:32px;">
                <div style="text-align:center;margin-bottom:24px;">
                    <div style="font-size:24px;font-weight:800;color:var(--accent);">量化交易系统</div>
                    <div style="font-size:12px;color:var(--text-muted);margin-top:4px;">请登录以继续</div>
                </div>
                <div class="form-group">
                    <label class="form-label">用户名</label>
                    <input class="form-input" id="loginUser" value="admin" autocomplete="username">
                </div>
                <div class="form-group">
                    <label class="form-label">密码</label>
                    <input class="form-input" id="loginPass" type="password" autocomplete="current-password">
                </div>
                <div id="loginError" style="color:var(--red);font-size:12px;margin-bottom:8px;display:none;"></div>
                <button class="btn btn-primary" id="btnLogin" style="width:100%;padding:10px;">登录</button>
            </div>
        </div>
    `;

    const doLogin = async () => {
        const user = document.getElementById('loginUser').value;
        const pass = document.getElementById('loginPass').value;
        const errEl = document.getElementById('loginError');
        errEl.style.display = 'none';

        try {
            const resp = await login(user, pass);
            if (resp.error) {
                errEl.textContent = resp.error;
                errEl.style.display = 'block';
                return;
            }
            setToken(resp.data.token);
            window.location.hash = '#/platform';
        } catch (e) {
            errEl.textContent = '登录失败: ' + e.message;
            errEl.style.display = 'block';
        }
    };

    document.getElementById('btnLogin').addEventListener('click', doLogin);
    document.getElementById('loginPass').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doLogin();
    });
    document.getElementById('loginPass').focus();
}

export function destroy() {}
