const assert = require('node:assert/strict');
const graph = require('../static/js/cluster_graph.js');
const nodes = [{id:'company:1', kind:'company', name:'A'}, {id:'contact:1', kind:'contact', name:'Shared'}, {id:'company:2', kind:'company', name:'B'}, {id:'company:3', kind:'company', name:'C'}];
const links = [{id:'e1',source:'company:1',target:'contact:1',type:'email'}, {id:'e2',source:'company:2',target:'contact:1',type:'email'}];
assert.deepEqual(graph.shortestPath(nodes, links, 'company:1', 'company:2'), {nodes:['company:1','contact:1','company:2'],edges:['e1','e2']});
assert.equal(graph.shortestPath(nodes, links, 'company:1', 'company:2', ['director']), null);
assert.equal(graph.shortestPath(nodes, links, 'company:1', 'company:3'), null);
assert.equal(graph.shortestPath(nodes, links, 'unknown', 'company:2'), null);
const saved = {positions: {'company:1': {x:100,y:200,pinned:true}, 'contact:1':{x:350,y:200,pinned:false}, 'old-node':{x:0,y:0,pinned:true}}};
const restored = graph.restorePositions(nodes.map(node => ({...node})), links, saved);
assert.equal(restored[0].x, 100); assert.equal(restored[0].y, 200); assert.equal(restored[0].pinned,true);
assert.equal(restored[1].x, 350); assert.equal(restored[1].y, 200);
assert.ok(Number.isFinite(restored[2].x) && Math.abs(restored[2].x - 350) < 350, 'New connected node starts near a saved neighbour');
const poisoned = graph.restorePositions(nodes.map(node => ({...node})), links, {positions:{'company:1':{x:Infinity,y:NaN}}});
assert.ok(poisoned.every(node => Number.isFinite(node.x) && Number.isFinite(node.y)));
for (const name of ['A'.repeat(250), 'An extremely long fixture company name with international branches and manufacturing services', '测试'.repeat(100)]) {
    const lines = graph.wrappedLabel(name); assert.ok(lines.length <= 5); assert.ok(lines.every(line => Array.from(line).length <= 24));
}
const payload = '<img src=x onerror=alert(1)>';
const element = {set textContent(value) { this.value = value; }, set innerHTML(_) { throw Error('HTML sink used'); }};
graph.writeText(element, payload); assert.equal(element.value,payload);
for (const url of ['javascript:alert(1)', 'data:text/html,x', '//evil.example', '/\\evil.example']) assert.equal(graph.safeLink(url), null);
assert.equal(graph.safeLink('/companies/1/'),'/companies/1/');
assert.equal(graph.safeLink('https://example.org/source'),'https://example.org/source');
for (const size of [8, 50, 500]) {
    const fixture = Array.from({length:size},(_,i)=>({id:'company:'+i,kind:'company'})); fixture.push({id:'contact:1',kind:'contact'});
    const edges = fixture.slice(0,-1).map((node,i)=>({id:'e'+i,source:node.id,target:'contact:1',type:'address'}));
    assert.equal(graph.shortestPath(fixture,edges,'company:0','company:'+(size-1)).edges.length,2);
    assert.equal(graph.adjacency(fixture,edges).get('contact:1').length,size);
}
console.log('PASS: paths and filters, layout reuse/new nodes, long labels, literal text, safe links, 8/50/500-node graphs.');
