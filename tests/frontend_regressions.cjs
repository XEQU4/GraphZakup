// Offline behavior regressions for the current UI; no npm install required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

async function flushPromises() {
    for (let i = 0; i < 8; i++) await Promise.resolve();
}

async function testSearch(filename, prefix, bodyId, paginationId, row) {
    const elements = new Map();
    function element(id) {
        if (!elements.has(id)) elements.set(id, {
            innerHTML: `initial:${id}`, textContent: '10', value: '', className: '',
            style: {}, handlers: {}, focus() {},
            addEventListener(name, callback) { this.handlers[name] = callback; },
        });
        return elements.get(id);
    }
    const input = element(`${prefix}-search`);
    const clear = element(`${prefix}-search-clear`);
    const body = element(bodyId);
    const spinner = element(`${prefix}-search-spinner`);
    const original = body.innerHTML;
    const timers = new Map();
    const requests = [];
    let nextTimer = 0;
    const context = {
        document: {getElementById: element}, window: {location: {pathname: '/synthetic/'}},
        AbortController, console,
        setTimeout(callback) { timers.set(++nextTimer, callback); return nextTimer; },
        clearTimeout(id) { timers.delete(id); },
        fetch() { return new Promise(resolve => requests.push(resolve)); },
    };
    vm.runInNewContext(fs.readFileSync(filename, 'utf8'), context, {filename});
    function search(value) {
        input.value = value;
        input.handlers.input.call(input);
        for (const [id, callback] of timers) { timers.delete(id); callback(); }
    }
    function finish(index, results) {
        requests[index]({ok: true, json: () => Promise.resolve({results})});
    }
    search('first');
    clear.handlers.click.call(clear);
    finish(0, [row]);
    await flushPromises();
    assert.equal(body.innerHTML, original, `${filename}: late response after clear`);
    assert.equal(spinner.style.display, 'none');

    search('old');
    search('new');
    finish(1, [row]);
    await flushPromises();
    assert.equal(body.innerHTML, original, `${filename}: obsolete response`);
    finish(2, [row]);
    await flushPromises();
    assert.ok(body.innerHTML.includes('&lt;img'), `${filename}: source text escaped`);
    assert.ok(!body.innerHTML.includes('<img'), `${filename}: no executable source HTML`);
    assert.equal(spinner.style.display, 'none');
    assert.equal(element(paginationId).style.display, 'none');
}

function testGraphTooltip() {
    const payload = '<img src=x onerror=alert(1)>';
    const data = {nodes: [{id: 'company:1', name: payload, kind:'company', bin:'000000000001', url:'/companies/1/'}], links: []};
    const callbacks = [], textWrites = [], htmlWrites = [];
    let chain;
    chain = new Proxy({}, {get(_, method) { return (...args) => {
        if (method === 'on' && args[0] === 'mouseover') callbacks.push(args[1]);
        if (method === 'text' && typeof args[0] !== 'function') textWrites.push(args[0]);
        if (method === 'html') htmlWrites.push(args[0]);
        return chain;
    }; }});
    const d3 = {};
    for (const name of ['select','forceSimulation','forceLink','forceManyBody','forceCenter','forceCollide','drag','zoom']) d3[name] = () => chain;
    d3.zoomIdentity = chain; d3.zoomTransform = () => ({x:0,y:0,k:1});
    const element = () => ({textContent:'', addEventListener(){}, setAttribute(){}, replaceChildren(){}, appendChild(item){return item;}});
    const elements = new Map();
    const context = {d3, console, window:{d3, location:{}}, document:{
        getElementById(id) {
            if (id === 'graph-rebuild') return null;
            if (!elements.has(id)) elements.set(id,element());
            const item = elements.get(id);
            if (id === 'graph') Object.assign(item,{dataset:{},clientWidth:800,clientHeight:640});
            if (id === 'graph-data') item.textContent = JSON.stringify(data);
            if (id === 'graph-options') item.textContent = JSON.stringify({cluster_id:'fixture',view:{revision:0,payload:null},authenticated:false});
            return item;
        }, querySelectorAll(){return [];}, createElement:element, createTextNode(value){return {textContent:value};},
    }};
    vm.runInNewContext(fs.readFileSync('static/js/cluster_graph.js','utf8'),context);
    assert.equal(callbacks.length,2);
    const event = {offsetX:0,offsetY:0};
    callbacks[0].call({},event,{type:payload,value:payload,confidence:'.250'});
    callbacks[1].call({},event,data.nodes[0]);
    assert.equal(htmlWrites.length,0,'Graph source data must not reach an HTML sink');
    assert.ok(textWrites.some(text => String(text).includes(payload)),'Malicious name remains literal tooltip text');
}
(async () => {
    const payload = '<img src=x onerror=alert(1)>';
    await testSearch('static/js/search_companies.js', 'companies', 'companies-tbody', 'pagination-wrap', {
        name: payload, bin: '000000000001', url: '/companies/1/',
        director_html: '<span>Escaped on server</span>', contracts_count: 1, badge_html: '<span>0/100</span>',
    });
    await testSearch('static/js/search_owners.js', 'owners', 'owners-tbody', 'pagination-wrap', {
        full_name: payload, url: '/owners/1/', companies_count: 1, companies_html: '<span>Escaped on server</span>',
    });
    await testSearch('static/js/search_dashboard.js', 'contract', 'contracts-tbody', 'contracts-pagination', {
        title: payload, supplier_name: payload, supplier_url: '/companies/1/', customer: payload,
        amount: '12.34', date: '2026-01-01', number_html: '<span>Escaped on server</span>',
    });
    testGraphTooltip();
    console.log('PASS: three searches escape source text and reject obsolete responses; graph tooltips render literal text.');
})().catch(error => { console.error(error); process.exitCode = 1; });

