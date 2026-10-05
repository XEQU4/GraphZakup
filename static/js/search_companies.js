(
    function () {
        const input = document.getElementById('companies-search');
        const tbody = document.getElementById('companies-tbody');
        const clearBtn = document.getElementById('companies-search-clear');
        const spinner = document.getElementById('companies-search-spinner');
        const hint = document.getElementById('companies-search-hint');
        const paginationWrap = document.getElementById('pagination-wrap');
        const totalCount = document.getElementById('total-count');

        // Preserve the initial state on page load
        const originalTbody = tbody.innerHTML;
        const originalPagination = paginationWrap.innerHTML;
        const originalCount = totalCount.textContent;

        let timer, controller;
        let requestVersion = 0;
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
                tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted p-4">Nothing found</td></tr>';
                hint.textContent = 'No results';
                hint.className = 'gz-search-hint no-results';
                return;
            }
            hint.textContent = `Found: ${rows.length}${rows.length === 50 ? '+' : ''}`;
            hint.className = 'gz-search-hint has-results';

            tbody.innerHTML = rows.map(r => `
            <tr>
                <td class="ps-3"><a href="${escHtml(r.url)}" class="fw-semibold">${escHtml(r.name)}</a></td>
                <td class="text-light fw-monospace">${escHtml(r.bin)}</td>
                <td>${r.director_html}</td>
                <td class="text-center fw-bold text-success">${escHtml(r.contracts_count)}</td>
                <td class="pe-3">${r.badge_html}</td>
            </tr>
        `).join('');
        }

        function escHtml(s) {
            return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
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
                        hint.textContent = 'Search failed';
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
            timer = setTimeout(() => doSearch(q), DELAY);
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

        // Init state if pre-filled (from back navigation)
        if (input.value.trim()) {
            toggleClear(true);
            hint.textContent = '';
        }
    }
)
();
