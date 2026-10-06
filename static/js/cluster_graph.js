/* Saved evidence renderer. Source values only enter text nodes. */
(function (root) {
    'use strict';
    const TYPES = ['director', 'owner', 'address', 'phone', 'email'];
    const nodeId = node => typeof node === 'object' ? node.id : node;
    function wrappedLabel(value, width = 24, maxLines = 5) {
        const words = String(value).split(/\s+/).flatMap(word => {
            const chars = Array.from(word), chunks = [];
            for (let i = 0; i < chars.length; i += width) chunks.push(chars.slice(i, i + width).join(''));
            return chunks;
        });
        const lines = [''];
        for (const word of words) {
            if (lines[lines.length - 1] && lines[lines.length - 1].length + word.length + 1 > width) lines.push('');
            lines[lines.length - 1] += (lines[lines.length - 1] ? ' ' : '') + word;
        }
        if (lines.length > maxLines) return [...lines.slice(0, maxLines - 1), lines[maxLines - 1].slice(0, width - 1) + '…'];
        return lines;
    }
    function adjacency(nodes, links, filters = TYPES) {
        const map = new Map(nodes.map(node => [node.id, []]));
        for (const edge of links) {
            if (!filters.includes(edge.type)) continue;
            const source = nodeId(edge.source), target = nodeId(edge.target);
            if (map.has(source) && map.has(target)) {
                map.get(source).push({node: target, edge});
                map.get(target).push({node: source, edge});
            }
        }
        return map;
    }
    function shortestPath(nodes, links, from, to, filters = TYPES) {
        const map = adjacency(nodes, links, filters), previous = new Map([[from, null]]), queue = [from];
        if (!map.has(from) || !map.has(to)) return null;
        for (let index = 0; index < queue.length && !previous.has(to); index++) {
            for (const item of map.get(queue[index])) {
                if (!previous.has(item.node)) { previous.set(item.node, {from: queue[index], edge: item.edge.id}); queue.push(item.node); }
            }
        }
        if (!previous.has(to)) return null;
        const path = {nodes: [to], edges: []};
        while (path.nodes[0] !== from) {
            const step = previous.get(path.nodes[0]);
            path.edges.unshift(step.edge); path.nodes.unshift(step.from);
        }
        return path;
    }
    function restorePositions(nodes, links, payload) {
        const positions = payload && payload.positions || {}, byId = new Map(nodes.map(node => [node.id, node]));
        const valid = value => value && Number.isFinite(value.x) && Number.isFinite(value.y) && Math.abs(value.x) <= 1e6 && Math.abs(value.y) <= 1e6;
        const neighbours = adjacency(nodes, links);
        const saved = new Set();
        for (const node of nodes) {
            if (valid(positions[node.id])) {
                Object.assign(node, {x: positions[node.id].x, y: positions[node.id].y, pinned: positions[node.id].pinned === true});
                saved.add(node.id);
            }
        }
        const grid = new Map(), spacing = 250;
        const cellKey = (x,y) => Math.floor(x / spacing) + ':' + Math.floor(y / spacing);
        function record(node) { const key = cellKey(node.x,node.y); if (!grid.has(key)) grid.set(key,[]); grid.get(key).push(node); }
        function crowded(x,y) {
            const cx = Math.floor(x / spacing), cy = Math.floor(y / spacing);
            for (let dx=-1; dx<=1; dx++) for (let dy=-1; dy<=1; dy++) {
                for (const other of grid.get((cx+dx)+':'+(cy+dy)) || []) if (Math.hypot(x-other.x,y-other.y) < spacing) return true;
            }
            return false;
        }
        nodes.filter(node => saved.has(node.id)).forEach(record);
        nodes.forEach((node,index) => {
            if (saved.has(node.id)) return;
            const anchors = neighbours.get(node.id).filter(item => saved.has(item.node)).map(item => byId.get(item.node));
            const centreX = anchors.length ? anchors.reduce((sum,item)=>sum+item.x,0)/anchors.length : 0;
            const centreY = anchors.length ? anchors.reduce((sum,item)=>sum+item.y,0)/anchors.length : 0;
            for (let attempt=0; attempt<48; attempt++) {
                const angle = index*2.399963 + attempt*.618;
                const radius = (anchors.length ? 300 : Math.max(180,Math.sqrt(index+1)*120)) + Math.floor(attempt/8)*160;
                node.x = centreX + Math.cos(angle)*radius; node.y = centreY + Math.sin(angle)*radius;
                if (!crowded(node.x,node.y)) break;
            }
            node.pinned=false; record(node);
        });        return nodes;
    }
    function safeLink(url) {
        return typeof url === 'string' && !/[\s\u0000-\u001f\u007f]/.test(url) && ((url.startsWith('/') && !url.startsWith('//') && !url.includes('\\')) || /^https:\/\/[^\s]+$/.test(url)) ? url : null;
    }
    function writeText(element, value) { element.textContent = String(value); return element; }
    const helpers = {wrappedLabel, adjacency, shortestPath, restorePositions, safeLink, writeText};
    if (typeof module !== 'undefined' && module.exports) { module.exports = helpers; return; }
    root.GraphTools = helpers;
    if (typeof document === 'undefined') return;
    const el = id => document.getElementById(id);
    const container = el('graph');
    if (!container) return;
    const status = message => writeText(el('graph-status'), message);
    let graph, options;
    try { graph = JSON.parse(el('graph-data').textContent); options = JSON.parse(el('graph-options').textContent); }
    catch (_) { status('The saved graph could not be read.'); return; }
    if (!graph.nodes.length) { status('No nodes in this saved version.'); return; }
    if (!root.d3) { status('The graph renderer could not load. Saved graph JSON remains available.'); return; }
    const d3 = root.d3, nodes = graph.nodes.map(node => ({...node})), links = graph.links.map(edge => ({...edge}));
    const byId = new Map(nodes.map(node => [node.id, node]));
    const motionMS = root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 350;
    const metrics = el('graph-metrics');
    if (metrics) {
        for (const [label, count] of [['companies', nodes.filter(node => node.kind === 'company').length],
            ['people', nodes.filter(node => node.kind === 'person').length], ['contacts', nodes.filter(node => node.kind === 'contact').length], ['relationships', links.length]]) {
            const chip = document.createElement('span'), total = writeText(document.createElement('strong'), count);
            chip.appendChild(total); chip.appendChild(document.createTextNode(label)); metrics.appendChild(chip);
        }
    }
    const localKey = 'grafzakup.graph-view.v1.' + options.cluster_id;
    let saved = options.view.payload, revision = options.view.revision || 0;
    if (!options.authenticated) { try { saved = JSON.parse(localStorage.getItem(localKey)); } catch (_) { saved = null; } }
    let selected = null, selectedEdge = null, pathStart = null, path = null;
    let frozen = saved ? saved.frozen !== false : false;
    if (motionMS === 0) frozen = true;
    let filters = saved && Array.isArray(saved.filters) ? saved.filters.filter(type => TYPES.includes(type)) : [...TYPES];
    restorePositions(nodes, links, saved);
    const svg = d3.select(container).append('svg').attr('aria-label', 'Companies, verified people and shared contacts');
    const defs = svg.append('defs');
    for (const [id, from, to] of [['company', '#203c60', '#142740'], ['person', '#39305f', '#201e38'], ['contact', '#2c3140', '#182130']]) {
        const gradient = defs.append('linearGradient').attr('id', 'graph-' + id + '-fill').attr('x1', '0%').attr('y1', '0%').attr('x2', '100%').attr('y2', '100%');
        gradient.append('stop').attr('offset', '0%').attr('stop-color', from);
        gradient.append('stop').attr('offset', '100%').attr('stop-color', to);
    }
    const layer = svg.append('g');
    const tooltip = d3.select(container).append('div').attr('class', 'graph-tooltip').style('display', 'none');
    const zoom = d3.zoom().scaleExtent([0.05, 8]).on('zoom', event => layer.attr('transform', event.transform));
    svg.call(zoom).on('dblclick.zoom', null);
    const line = layer.append('g').selectAll('path').data(links).join('path').attr('class', edge => 'graph-link edge-' + edge.type + (['address', 'phone', 'email'].includes(edge.type) ? ' weak' : ''))
        .attr('tabindex', 0).attr('role', 'button').attr('aria-label', edge => edge.type + ': ' + edge.value)
        .on('click', (_, edge) => inspectEdge(edge)).on('keydown', (event, edge) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); inspectEdge(edge); } })
        .on('mouseover', (event, edge) => showTooltip(event, edge.type + ': ' + edge.value + ' · confidence ' + edge.confidence))
        .on('mouseout', () => tooltip.style('display', 'none'));
    const edgeLabel = layer.append('g').selectAll('g').data(links).join('g').attr('class', edge => 'graph-edge-label edge-' + edge.type).on('click', (_, edge) => inspectEdge(edge));
    edgeLabel.append('rect').attr('x', -32).attr('y', -11).attr('width', 64).attr('height', 22).attr('rx', 8);
    edgeLabel.append('text').attr('text-anchor', 'middle').attr('y', 4).text(edge => edge.type);
    const groups = layer.append('g').selectAll('g').data(nodes).join('g').attr('class', node => 'graph-node node-' + node.kind + (node.contact_type ? ' edge-' + node.contact_type : '')).attr('tabindex', 0).attr('role', 'button')
        .attr('aria-label', node => node.kind + ': ' + node.name)
        .on('click', (event, node) => { if (!event.defaultPrevented) { selectNode(node.id); if (d3.zoomTransform(svg.node()).k < .6) focusNode(node); } })
        .on('keydown', (event, node) => {
            if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectNode(node.id); }
            if (event.key.toLowerCase() === 'p') { node.pinned = !node.pinned; applyFrozen(); updateHighlights(); }
        })
        .on('dblclick', (event, node) => { event.preventDefault(); node.pinned = !node.pinned; applyFrozen(); updateHighlights(); status(node.pinned ? 'Node pinned.' : 'Node unpinned.'); })
        .on('mouseover', (event, node) => showTooltip(event, node.kind + ': ' + node.name))
        .on('mouseout', () => tooltip.style('display', 'none'));
    groups.each(function (node) {
        const group = d3.select(this);
        if (node.kind === 'company') {
            group.append('rect').attr('x', -112).attr('y', -65).attr('width', 224).attr('height', 130).attr('rx', 16).attr('class', 'node-shape');
            group.append('path').attr('d', 'M-98,-49h12v16h-12z M-94,-45h4 M-94,-41h4 M-94,-37h4').attr('class', 'node-icon');
            group.append('line').attr('x1', -98).attr('x2', 98).attr('y1', -26).attr('y2', -26).attr('class', 'node-divider');
            group.append('text').attr('x', -75).attr('y', -38).attr('class', 'node-category').text('COMPANY');
        } else if (node.kind === 'person') {
            group.append('circle').attr('r', 90).attr('class', 'node-shape');
            group.append('path').attr('d', 'M-6,-58a6,6 0 1,0 12,0a6,6 0 1,0 -12,0 M-13,-39q0,-12 13,-12q13,0 13,12').attr('class', 'node-icon');
        } else {
            group.append('path').attr('d', 'M-83,-60 Q-95,-60 -101,-48 L-118,-8 Q-122,0 -118,8 L-101,48 Q-95,60 -83,60 L83,60 Q95,60 101,48 L118,8 Q122,0 118,-8 L101,-48 Q95,-60 83,-60 Z').attr('class', 'node-shape');
            group.append('text').attr('text-anchor', 'middle').attr('y', -36).attr('class', 'node-category').text(node.contact_type.toUpperCase());
        }
        group.append('title').text(node.name);
        const lines = wrappedLabel(node.name, node.kind === 'person' ? 22 : 28, 3);
        const text = group.append('text').attr('text-anchor', 'middle');
        lines.forEach((value, index) => text.append('tspan').attr('x', 0).attr('y', (index - (lines.length - 1) / 2) * 17 + (node.kind === 'person' ? 9 : 1)).text(value));
        group.append('text').attr('text-anchor', 'middle').attr('y', node.kind === 'person' ? 60 : 48).attr('class', 'node-meta')
            .text(node.kind === 'company' ? 'BIN ' + node.bin : node.kind === 'person' ? 'IDENTITY VERIFIED' : 'SHARED CONTACT · WEAK EVIDENCE');
    });
    groups.attr('opacity', 0).transition().duration(motionMS * 2).attr('opacity', 1);
    const simulation = d3.forceSimulation(nodes).force('link', d3.forceLink(links).id(node => node.id).distance(340))
        .force('charge', d3.forceManyBody().strength(-1300)).force('collide', d3.forceCollide(145))
        .force('center', d3.forceCenter(0, 0)).on('tick', render);
    if (motionMS === 0 && !saved) simulation.stop().tick(180);
    groups.call(d3.drag().on('start', (event, node) => { if (!event.active && !frozen) simulation.alphaTarget(0.1).restart(); node.fx = node.x; node.fy = node.y; })
        .on('drag', (event, node) => { node.fx = event.x; node.fy = event.y; node.x = event.x; node.y = event.y; render(); })
        .on('end', (event, node) => { if (!event.active) simulation.alphaTarget(0); if (!frozen && !node.pinned) { node.fx = null; node.fy = null; } }));
    function showTooltip(event, value) { tooltip.text(value).style('left', Math.min(event.offsetX + 12, container.clientWidth - 180) + 'px').style('top', (event.offsetY + 12) + 'px').style('display', 'block'); }
    function render() {
        line.attr('d', edge => {
            const a = edge.source, b = edge.target, offset = edge.type === 'owner' ? 35 : 0;
            return 'M' + a.x + ',' + a.y + ' Q' + ((a.x + b.x) / 2 + offset) + ',' + ((a.y + b.y) / 2 - offset) + ' ' + b.x + ',' + b.y;
        });
        edgeLabel.attr('transform', edge => 'translate(' + ((edge.source.x + edge.target.x) / 2 + (edge.type === 'owner' ? 18 : 0)) + ',' + ((edge.source.y + edge.target.y) / 2 - (edge.type === 'owner' ? 18 : 0)) + ')');
        groups.attr('transform', node => 'translate(' + node.x + ',' + node.y + ')');
    }
    function applyFrozen() {
        nodes.forEach(node => { node.fx = frozen || node.pinned ? node.x : null; node.fy = frozen || node.pinned ? node.y : null; });
        writeText(el('graph-freeze'), frozen ? 'Resume layout' : 'Freeze positions');
        el('graph-freeze').setAttribute('aria-pressed', String(frozen));
        if (frozen) simulation.stop(); else simulation.alpha(0.3).restart();
        render();
    }
    function updateHighlights() {
        const neighbours = adjacency(nodes, links, filters);
        const close = new Set(selected && neighbours.has(selected) ? neighbours.get(selected).map(item => item.node) : []);
        const activeNodes = new Set(links.filter(edge => filters.includes(edge.type)).flatMap(edge => [nodeId(edge.source), nodeId(edge.target)]));
        groups.style('display', node => node.kind === 'company' || activeNodes.has(node.id) || node.id === selected ? null : 'none')
            .attr('tabindex', node => node.kind === 'company' || activeNodes.has(node.id) || node.id === selected ? 0 : -1)
            .classed('selected', node => node.id === selected || !!(path && path.nodes.includes(node.id)))
            .classed('neighbour', node => close.has(node.id)).classed('pinned', node => node.pinned)
            .classed('graph-dimmed', node => !!selected && node.id !== selected && !close.has(node.id) && !(path && path.nodes.includes(node.id)));
        const highlight = edge => edge.id === selectedEdge || !!(path && path.edges.includes(edge.id));
        line.style('display', edge => filters.includes(edge.type) ? null : 'none').attr('tabindex', edge => filters.includes(edge.type) ? 0 : -1)
            .classed('selected', highlight).classed('graph-dimmed', edge => !!selected && nodeId(edge.source) !== selected && nodeId(edge.target) !== selected && !highlight(edge));
        edgeLabel.style('display', edge => filters.includes(edge.type) ? null : 'none').classed('graph-dimmed', edge => !!selected && nodeId(edge.source) !== selected && nodeId(edge.target) !== selected && !highlight(edge));
    }
    const inspector = el('graph-inspector-content');
    function add(tag, text, parent = inspector) { return parent.appendChild(writeText(document.createElement(tag), text)); }
    function button(text, action) { const item = add('button', text); item.type = 'button'; item.className = 'btn btn-sm btn-outline-light'; item.addEventListener('click', action); return item; }
    function reference(text, url) { const valid = safeLink(url); if (!valid) { add('p', text); return; } const link = add('a', text); link.href = valid; link.rel = 'noopener noreferrer'; if (valid.startsWith('https:')) link.target = '_blank'; }
    function inspectEdge(edge) {
        selected = nodeId(edge.source); selectedEdge = edge.id; path = null;
        inspector.replaceChildren(); add('h4', edge.type, inspector).className = 'h6';
        add('p', byId.get(nodeId(edge.source)).name + ' → ' + byId.get(nodeId(edge.target)).name);
        add('p', 'Relationship in saved graph v' + options.version + '. ' + (['owner', 'director'].includes(edge.type) ? 'Verified identity and source-backed role.' : 'Shared contact; affiliation and wrongdoing are not established.'));
        add('p', 'Value: ' + edge.value); add('p', 'Evidence confidence: ' + edge.confidence);
        add('p', 'Legal interval: ' + (edge.valid_from || 'unknown') + ' to ' + (edge.valid_until || 'unknown') + ' (exclusive end)');
        edge.limitations.forEach(text => add('p', text));
        for (const item of edge.evidence) {
            add('p', item.quality + ' · observed ' + (item.observed_at || 'unknown'));
            reference(item.source + (item.observation_id ? ' · observation ' + item.observation_id : ''), item.url);
        }
        updateHighlights();
    }
    function selectNode(id) {
        selected = id; selectedEdge = null;
        path = pathStart && pathStart !== id ? shortestPath(nodes, links, pathStart, id, filters) : null;
        const node = byId.get(id); inspector.replaceChildren(); add('h4', node.name).className = 'h6'; add('p', node.kind + (node.bin ? ' · BIN ' + node.bin : ''));
        if (node.url) reference('Open company', node.url);
        const direct = adjacency(nodes, links, filters).get(id);
        const relatedCompanies = new Set();
        const neighbours = adjacency(nodes, links, filters);
        for (const item of direct) {
            if (byId.get(item.node).kind === 'company') relatedCompanies.add(item.node);
            else for (const next of neighbours.get(item.node)) if (byId.get(next.node).kind === 'company' && next.node !== id) relatedCompanies.add(next.node);
        }
        add('p', direct.length + ' direct relationships · ' + relatedCompanies.size + ' connected companies under the current filters.');
        button('Focus this node', () => focusNode(node));
        if (pathStart && pathStart !== id) {
            add('p', path ? 'Path (' + path.edges.length + ' relationships): ' + path.nodes.map(key => byId.get(key).name).join(' → ') + '. This is a path, not a direct company relationship.' : 'No path under the current filters.');
            if (path) path.edges.forEach(key => { const edge = links.find(item => item.id === key); button('Inspect path evidence: ' + edge.type, () => inspectEdge(edge)); });
        }
        button('Use as path start', () => { pathStart = id; status('Path start selected. Select another node to inspect a path.'); });
        button(node.pinned ? 'Unpin node' : 'Pin node', () => { node.pinned = !node.pinned; applyFrozen(); selectNode(id); });
        add('p', 'Direct relationships:');
        for (const item of direct) button(item.edge.type + ' → ' + byId.get(item.node).name, () => inspectEdge(item.edge));
        if (node.kind === 'company' && relatedCompanies.size) {
            add('p', 'Companies connected through a shared feature:');
            for (const key of relatedCompanies) button(byId.get(key).name, () => { pathStart = id; selectNode(key); focusNode(byId.get(key)); });
        }
        updateHighlights(); status('Selected ' + node.name);
    }
    function fit() {
        const width = container.clientWidth, height = container.clientHeight;
        const xs = nodes.map(node => node.x), ys = nodes.map(node => node.y);
        const minX = Math.min(...xs) - 125, maxX = Math.max(...xs) + 125, minY = Math.min(...ys) - 105, maxY = Math.max(...ys) + 105;
        const k = Math.max(.05, Math.min(1.2, width / (maxX - minX), height / (maxY - minY)) * .9);
        svg.transition().duration(motionMS).call(zoom.transform, d3.zoomIdentity.translate(width / 2 - (maxX + minX) / 2 * k, height / 2 - (maxY + minY) / 2 * k).scale(k));
    }
    function focusNode(node) {
        const k = Math.max(.85, Math.min(1.3, d3.zoomTransform(svg.node()).k));
        svg.transition().duration(motionMS).call(zoom.transform, d3.zoomIdentity.translate(container.clientWidth / 2 - node.x * k, container.clientHeight / 2 - node.y * k).scale(k));
    }
    function restore() {
        restorePositions(nodes, links, saved); frozen = saved ? saved.frozen !== false : false;
        if (motionMS === 0) frozen = true;
        filters = saved && Array.isArray(saved.filters) ? saved.filters.filter(type => TYPES.includes(type)) : [...TYPES];
        document.querySelectorAll('.graph-filters input').forEach(input => { input.checked = filters.includes(input.value); });
        applyFrozen(); updateHighlights();
        const transform = saved && saved.zoom;
        if (transform && Number.isFinite(transform.x) && Number.isFinite(transform.y) && Number.isFinite(transform.k) && transform.k >= .05 && transform.k <= 8) svg.call(zoom.transform, d3.zoomIdentity.translate(transform.x, transform.y).scale(transform.k)); else fit();
        if (saved && byId.has(saved.selected)) selectNode(saved.selected);
        status(saved ? 'Saved view restored. New nodes were placed near saved neighbours.' : 'No saved view. Initial layout restored.');
    }
    function collectView() {
        const transform = d3.zoomTransform(svg.node());
        return {positions: Object.fromEntries(nodes.map(node => [node.id, {x: node.x, y: node.y, pinned: !!node.pinned}])),
            zoom: {x: transform.x, y: transform.y, k: transform.k}, filters, selected, frozen};
    }
    function csrf() { const item = document.querySelector('[name=csrfmiddlewaretoken]'); return item ? item.value : ''; }
    async function save() {
        const payload = collectView();
        if (!options.authenticated) { try { localStorage.setItem(localKey, JSON.stringify(payload)); saved = payload; status('View saved in this browser. Sign in to save across devices.'); } catch (_) { status('Browser storage is unavailable.'); } return; }
        if (options.historical) { status('Open the current graph version before saving a view.'); return; }
        try {
            const response = await fetch(container.dataset.viewUrl, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
                body: JSON.stringify({snapshot_id: options.snapshot_id, graph_hash: options.graph_hash, revision, payload})});
            const result = await response.json();
            if (!response.ok) { status(response.status === 409 ? 'Graph or view changed in another tab. Reload before saving.' : 'View could not be saved.'); return; }
            revision = result.revision; saved = result.payload; status('Personal view saved.');
        } catch (_) { status('View could not be saved. Check the connection.'); }
    }
    el('graph-fit').addEventListener('click', fit); el('graph-save').addEventListener('click', save); el('graph-restore').addEventListener('click', restore);
    el('graph-freeze').addEventListener('click', () => { frozen = !frozen; applyFrozen(); });
    el('graph-reset').addEventListener('click', () => { nodes.forEach(node => { node.pinned = false; }); restorePositions(nodes, links, null); frozen = false; applyFrozen(); fit(); status('Layout reset. Saved view is still available.'); });
    el('graph-clear-selection').addEventListener('click', () => { selected = selectedEdge = pathStart = path = null; inspector.replaceChildren(); add('p', 'Select a node or relationship.'); updateHighlights(); });
    document.querySelectorAll('.graph-filters input').forEach(input => input.addEventListener('change', () => {
        filters = Array.from(document.querySelectorAll('.graph-filters input:checked'), item => item.value); path = null; selectedEdge = null; updateHighlights(); if (selected) selectNode(selected);
    }));
    el('graph-search').addEventListener('input', event => {
        const query = event.target.value.trim().toLocaleLowerCase(), results = el('graph-results'); results.replaceChildren();
        if (!query) return;
        const matches = nodes.filter(node => (node.name + ' ' + (node.bin || '')).toLocaleLowerCase().includes(query));
        for (const node of matches.slice(0, 20)) {
            const item = writeText(document.createElement('button'), node.kind + ': ' + node.name); item.className = 'btn btn-sm btn-outline-light'; item.type = 'button';
            item.addEventListener('click', () => { selectNode(node.id); const k = Math.max(.65, d3.zoomTransform(svg.node()).k); svg.call(zoom.transform, d3.zoomIdentity.translate(container.clientWidth / 2 - node.x * k, container.clientHeight / 2 - node.y * k).scale(k)); }); results.appendChild(item);
        }
        status(matches.length + ' matching nodes; up to 20 shown.');
    });
    container.addEventListener('keydown', event => {
        if (event.target !== container) return;
        if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); svg.call(zoom.scaleBy, event.key === '-' ? .8 : 1.25); }
        const shifts = {ArrowLeft: [60, 0], ArrowRight: [-60, 0], ArrowUp: [0, 60], ArrowDown: [0, -60]};
        if (shifts[event.key]) { event.preventDefault(); const t = d3.zoomTransform(svg.node()); svg.call(zoom.translateBy, shifts[event.key][0] / t.k, shifts[event.key][1] / t.k); }
    });
    const rebuild = el('graph-rebuild');
    if (rebuild) rebuild.addEventListener('click', async () => {
        rebuild.disabled = true;
        try {
            const response = await fetch(container.dataset.rebuildUrl, {method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': csrf()}});
            if (!response.ok) throw new Error('request');
            const job = await response.json(); status('Recalculation requested. This uses saved data only.');
            const poll = async () => {
                try { const check = await fetch(job.url, {credentials: 'same-origin'}); if (!check.ok) throw new Error('status'); const result = await check.json();
                    if (['pending', 'running'].includes(result.status)) { status('Recalculation: ' + result.status); setTimeout(poll, 2000); }
                    else { status(result.status === 'succeeded' ? 'Recalculation complete. Reload to open the current version.' : 'Recalculation failed: ' + result.error); rebuild.disabled = false; }
                } catch (_) { status('Job status unavailable. Reload to check saved results.'); rebuild.disabled = false; }
            }; setTimeout(poll, 1000);
        } catch (_) { status('Recalculation could not be started.'); rebuild.disabled = false; }
    });
    for (const node of nodes.filter(node => node.kind === 'company')) { const li = document.createElement('li'), a = writeText(document.createElement('a'), node.name); a.href = safeLink(node.url) || '#'; li.appendChild(a); el('graph-company-list').appendChild(li); }
    if (typeof ResizeObserver !== 'undefined') new ResizeObserver(() => { svg.attr('viewBox', '0 0 ' + container.clientWidth + ' ' + container.clientHeight); }).observe(container);
    restore(); simulation.on('end', () => { if (!saved) fit(); }); updateHighlights();
})(typeof window !== 'undefined' ? window : globalThis);

