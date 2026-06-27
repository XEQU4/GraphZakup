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
        const BASE_URL = window.location.pathname;

        function toggleClear(v) {
            clearBtn.style.display = v ? 'block' : 'none';
        }

        function setLoading(on) {
            spinner.style.display = on ? 'block' : 'none';
            if (on) clearBtn.style.display = 'none';
        }

        function escHtml(s) {
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
                    <a href="${r.url}">${escHtml(r.full_name)}</a>
                </td>
                <td>${r.companies_count}</td>
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
                .then(r => r.json())
                .then(data => {
                    setLoading(false);
                    toggleClear(true);
                    renderRows(data.results);
                })
                .catch(err => {
                    if (err.name !== 'AbortError') {
                        setLoading(false);
                        hint.textContent = 'Ошибка поиска';
                        hint.className = 'gz-search-hint no-results';
                    }
                });
        }

        input.addEventListener('input', function () {
            const q = this.value.trim();
            toggleClear(q.length > 0);
            clearTimeout(timer);
            timer = setTimeout(() => doSearch(q), 300);
        });

        clearBtn.addEventListener('click', function () {
            input.value = '';
            toggleClear(false);
            restoreOriginal();
            input.focus();
        });

        if (input.value.trim()) toggleClear(true);
    }
)
();
