(
    function () {
        const input = document.getElementById('contract-search');
        const tbody = document.getElementById('contracts-tbody');
        const clearBtn = document.getElementById('contract-search-clear');
        const spinner = document.getElementById('contract-search-spinner');
        const pagination = document.getElementById('contracts-pagination');

        // Сохраняем исходное состояние при загрузке
        const originalTbody = tbody.innerHTML;
        const originalPagination = pagination.innerHTML;

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
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted p-4">Ничего не найдено</td></tr>';
                return;
            }
            tbody.innerHTML = rows.map(r => `
            <tr>
                <td class="ps-3 text-nowrap">${r.number_html}</td>
                <td>${escHtml(r.title)}</td>
                <td><a href="${r.supplier_url}" class="text-white border-bottom border-secondary text-decoration-none fw-semibold">${escHtml(r.supplier_name)}</a></td>
                <td>${escHtml(r.customer)}</td>
                <td class="text-end text-nowrap text-success fw-bold">${escHtml(r.amount)} ₸</td>
                <td class="pe-3 text-nowrap">${escHtml(r.date)}</td>
            </tr>
        `).join('');
        }

        function restoreOriginal() {
            tbody.innerHTML = originalTbody;
            pagination.innerHTML = originalPagination;
            pagination.style.display = '';
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
            pagination.style.display = 'none';

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
