(
    function () {
        const input = document.getElementById('companies-search');
        const tbody = document.getElementById('companies-tbody');
        const clearBtn = document.getElementById('companies-search-clear');
        const spinner = document.getElementById('companies-search-spinner');
        const hint = document.getElementById('companies-search-hint');
        const paginationWrap = document.getElementById('pagination-wrap');
        const totalCount = document.getElementById('total-count');

        // Сохраняем исходное состояние при загрузке
        const originalTbody = tbody.innerHTML;
        const originalPagination = paginationWrap.innerHTML;
        const originalCount = totalCount.textContent;

        let timer, controller;
        const DELAY = 300;
        const BASE_URL = window.location.pathname;

        function toggleClear(val) {
            clearBtn.style.display = val ? 'block' : 'none';
        }

        function setLoading(on) {
            spinner.style.display = on ? 'block' : 'none';
            if (on) clearBtn.style.display = 'none';
        }

        function renderRows(rows) {
            if (!rows.length) {
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-4">Ничего не найдено</td></tr>';
                hint.textContent = 'Нет результатов';
                hint.className = 'gz-search-hint no-results';
                return;
            }
            hint.textContent = `Найдено: ${rows.length}${rows.length === 50 ? '+' : ''}`;
            hint.className = 'gz-search-hint has-results';

            tbody.innerHTML = rows.map(r => `
            <tr>
                <td class="ps-3"><a href="${r.url}" class="fw-semibold">${escHtml(r.name)}</a></td>
                <td class="text-light fw-monospace">${escHtml(r.bin)}</td>
                <td>${r.director_html}</td>
                <td class="text-center fw-bold text-success">${r.contracts_count}</td>
                <td class="pe-3">${r.badge_html}</td>
            </tr>
        `).join('');
        }

        function escHtml(s) {
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
            timer = setTimeout(() => doSearch(q), DELAY);
        });

        clearBtn.addEventListener('click', function () {
            input.value = '';
            toggleClear(false);
            restoreOriginal();
            input.focus();
        });

        // Init state if pre-filled (from back navigation)
        if (input.value.trim()) {
            toggleClear(true);
            hint.textContent = '';
        }
    }
)
();
