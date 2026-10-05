(
    function () {
        const input = document.getElementById('owners-search');
        const tbody = document.getElementById('owners-tbody');
        const clearBtn = document.getElementById('owners-search-clear');
        const spinner = document.getElementById('owners-search-spinner');
        const hint = document.getElementById('owners-search-hint');
        const paginationWrap = document.getElementById('pagination-wrap');
        const totalCount = document.getElementById('total-count');

        // Сохраняем исходное состояние при загрузке
        const originalTbody = tbody.innerHTML;
        const originalPagination = paginationWrap.innerHTML;
        const originalCount = totalCount.textContent;

        let timer, controller;
        let requestVersion = 0;
        const BASE_URL = window.location.pathname;

        function toggleClear(v) {
            clearBtn.style.display = v ? 'block' : 'none';
        }

        function setLoading(on) {
            spinner.style.display = on ? 'block' : 'none';
            if (on) clearBtn.style.display = 'none';
        }

        function escHtml(s) {
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }

        function renderRows(rows) {
            if (!rows.length) {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted p-4">Ничего не найдено</td></tr>';
                hint.textContent = 'Нет результатов';
                hint.className = 'gz-search-hint no-results';
                return;
            }
            hint.textContent = `Найдено: ${rows.length}${rows.length === 50 ? '+' : ''}`;
            hint.className = 'gz-search-hint has-results';
            tbody.innerHTML = rows.map(r => `
            <tr>
                <td class="ps-3 text-nowrap fw-semibold">
                    <a href="${escHtml(r.url)}">${escHtml(r.full_name)}</a>
                </td>
                <td>${escHtml(r.companies_count)}</td>
                <td class="pe-3" style="max-width:420px;color:#8b9ab0;font-size:0.9em;">
                    ${r.companies_html}
                </td>
            </tr>
        `).join('');
        }

        function restoreOriginal() {
            tbody.innerHTML = originalTbody;
            paginationWrap.innerHTML = originalPagination;
            paginationWrap.style.display = '';
            hint.textContent = '';
            hint.className = 'gz-search-hint';
        }

        function doSearch(q) {
            const version = ++requestVersion;
            if (controller) controller.abort();
            controller = new AbortController();

            if (!q) {
                setLoading(false);
                restoreOriginal();
                return;
            }

            setLoading(true);
            paginationWrap.style.display = 'none';

            fetch(`${BASE_URL}?format=json&q=${encodeURIComponent(q)}`, {signal: controller.signal})
                .then(r => {
                    if (!r.ok) throw new Error('Search failed');
                    return r.json();
                })
                .then(data => {
                    if (version !== requestVersion) return;
                    if (!Array.isArray(data.results)) throw new Error('Invalid search response');
                    setLoading(false);
                    toggleClear(true);
                    renderRows(data.results);
                })
                .catch(err => {
                    if (version === requestVersion && err.name !== 'AbortError') {
                        setLoading(false);
                        hint.textContent = 'Ошибка поиска';
                        hint.className = 'gz-search-hint no-results';
                    }
                });
        }

        input.addEventListener('input', function () {
            const q = this.value.trim();
            ++requestVersion;
            if (controller) controller.abort();
            setLoading(false);
            toggleClear(q.length > 0);
            clearTimeout(timer);
            timer = setTimeout(() => doSearch(q), 300);
        });

        clearBtn.addEventListener('click', function () {
            input.value = '';
            ++requestVersion;
            clearTimeout(timer);
            if (controller) controller.abort();
            setLoading(false);
            toggleClear(false);
            restoreOriginal();
            input.focus();
        });

        if (input.value.trim()) toggleClear(true);
    }
)
();
