const graphElement = document.getElementById("graph");
const companyUrl = graphElement ? graphElement.dataset.companyUrl : "/companies/";
const graphDataElement = document.getElementById("graph-data");

if (graphElement && graphDataElement) {

    let graphData = {"nodes": [], "links": []};
    try {
        graphData = JSON.parse(graphDataElement.textContent);
    } catch (e) {
        console.error("graph-data parse error:", e);
    }
    if (!graphData.nodes || !graphData.links) {
        graphData = {"nodes": [], "links": []};
    }

    // --- Параллельные связи ---
    const linkGroup = {};
    graphData.links.forEach(l => {
        const idA = typeof l.source === "object" ? l.source.id : l.source;
        const idB = typeof l.target === "object" ? l.target.id : l.target;
        const pairKey = idA < idB ? `${idA}-${idB}` : `${idB}-${idA}`;
        if (!linkGroup[pairKey]) linkGroup[pairKey] = [];
        linkGroup[pairKey].push(l);
    });
    Object.values(linkGroup).forEach(group => {
        group.forEach((l, i) => { l.curve_index = i; l.curve_total = group.length; });
    });

    const width  = graphElement.clientWidth || 800;
    const height = 600;

    const svg = d3.select("#graph")
        .append("svg")
        .attr("width", width)
        .attr("height", height)
        .style("overflow", "hidden");

    // ============================================================
    // DEFS
    // ============================================================
    const defs = svg.append("defs");

    // CSS-анимации
    defs.append("style").text(`
        @keyframes pulse-high {
            0%,100% { opacity: 1; }
            50%      { opacity: 0.7; }
        }
        @keyframes dash-flow {
            to { stroke-dashoffset: -24; }
        }
        @keyframes glitch-flicker {
            0%,92%,100% { opacity:1; }
            93%  { opacity:0.35; }
            95%  { opacity:1; }
            97%  { opacity:0.55; }
        }
        .node-pulse-high { animation: pulse-high 1.8s ease-in-out infinite; }
        .node-pulse-mid  { animation: pulse-high 3s   ease-in-out infinite; }
        .link-flow       { animation: dash-flow 1.4s linear infinite; }
        .glitch-node     { animation: glitch-flicker 9s step-end infinite; }
    `);

    // Drop shadow
    const ds = defs.append("filter").attr("id", "node-shadow");
    ds.append("feDropShadow")
        .attr("dx",0).attr("dy",2).attr("stdDeviation",4)
        .attr("flood-color","#000").attr("flood-opacity",0.8);

    // Glow фильтры
    const makeGlow = (id, r, g, b, std) => {
        const f = defs.append("filter").attr("id", id)
            .attr("x","-80%").attr("y","-80%").attr("width","260%").attr("height","260%");
        f.append("feColorMatrix").attr("type","matrix")
            .attr("values", `0 0 0 0 ${r}  0 0 0 0 ${g}  0 0 0 0 ${b}  0 0 0 22 -8`)
            .attr("result","col");
        f.append("feGaussianBlur").attr("in","col").attr("stdDeviation", std).attr("result","blur");
        const m = f.append("feMerge");
        m.append("feMergeNode").attr("in","blur");
        m.append("feMergeNode").attr("in","SourceGraphic");
    };
    makeGlow("glow-red",    0.86, 0.21, 0.27, 5);
    makeGlow("glow-yellow", 1.00, 0.76, 0.03, 4);
    makeGlow("glow-link",   1.00, 0.49, 0.08, 2.5);

    // Градиенты узлов
    [
        ["ng-high", "#ff4d60","#8b0000"],
        ["ng-mid",  "#ffd065","#9a6800"],
        ["ng-low",  "#34c38f","#0d5c3a"],
    ].forEach(([id, c1, c2]) => {
        const g = defs.append("radialGradient").attr("id",id)
            .attr("cx","35%").attr("cy","35%").attr("r","65%");
        g.append("stop").attr("offset","0%").attr("stop-color",c1);
        g.append("stop").attr("offset","100%").attr("stop-color",c2);
    });

    // ============================================================
    // ЕДИНЫЙ КОНТЕЙНЕР ДЛЯ ZOOM/PAN
    // ============================================================
    const container = svg.append("g").attr("class","zoom-container");

    // ============================================================
    // СТИЛИ СВЯЗЕЙ
    // ============================================================
    const LINK_STYLES = {
        owner:    { color:"#f1556c", dash:"8,3"    },
        director: { color:"#4aa3ff", dash:null      },
        address:  { color:"#ffd065", dash:"5,4"    },
        phone:    { color:"#fd7e14", dash:"3,3"    },
        email:    { color:"#9b6bff", dash:"6,2,2,2"},
        customer: { color:"#6c757d", dash:"4,4"    },
    };
    const LINK_LABELS = {
        owner:"Общий владелец", director:"Общий директор",
        address:"Общий адрес",  phone:"Общий телефон",
        email:"Общий email",    customer:"Общий заказчик",
    };
    const ls = t => LINK_STYLES[t] || LINK_STYLES.customer;

    const getNodeColor  = r => r >= 70 ? "#dc3545" : r >= 40 ? "#ffc107" : "#198754";
    const getNodeGrad   = r => r >= 70 ? "ng-high"  : r >= 40 ? "ng-mid"  : "ng-low";
    const getGlowFilter = r => r >= 70 ? "url(#glow-red)" : r >= 40 ? "url(#glow-yellow)" : null;
    const getNodeR      = r => r >= 70 ? 26 : r >= 40 ? 23 : 20;

    // ============================================================
    // СВЯЗИ (фон + основная линия) — рисуются ПЕРВЫМИ (под узлами)
    // ============================================================
    const linkBg = container.append("g").selectAll("path")
        .data(graphData.links).enter().append("path")
        .attr("fill","none")
        .attr("stroke", d => ls(d.type).color)
        .attr("stroke-width", 8)
        .attr("stroke-linecap","round")
        .attr("opacity", 0.10);

    const linkMain = container.append("g").selectAll("path")
        .data(graphData.links).enter().append("path")
        .attr("fill","none")
        .attr("stroke", d => ls(d.type).color)
        .attr("stroke-width", 2.5)
        .attr("stroke-linecap","round")
        .attr("stroke-dasharray", d => ls(d.type).dash || null)
        .attr("opacity", 0.9)
        .attr("filter","url(#glow-link)")
        .classed("link-flow", d => !!ls(d.type).dash)
        .style("cursor","pointer");

    // ============================================================
    // УЗЛЫ — группы <g> поверх связей
    // ============================================================
    const nodeGroups = container.append("g").selectAll("g")
        .data(graphData.nodes).enter().append("g")
        .style("cursor","pointer");

    // Внешнее кольцо
    nodeGroups.append("circle")
        .attr("r", d => getNodeR(d.risk) + 7)
        .attr("fill","none")
        .attr("stroke", d => getNodeColor(d.risk))
        .attr("stroke-width", 1)
        .attr("opacity", 0.4)
        .attr("class", d => d.risk >= 70 ? "node-pulse-high glitch-node" : d.risk >= 40 ? "node-pulse-mid" : "");

    // Основной круг
    nodeGroups.append("circle")
        .attr("r", d => getNodeR(d.risk))
        .attr("fill", d => `url(#${getNodeGrad(d.risk)})`)
        .attr("stroke", d => getNodeColor(d.risk))
        .attr("stroke-width", 2)
        .attr("filter","url(#node-shadow)")
        .attr("class", d => d.risk >= 70 ? "node-pulse-high" : "");

    // Иконка внутри
    nodeGroups.append("text")
        .text(d => d.risk >= 70 ? "!" : d.risk >= 40 ? "~" : "✓")
        .attr("text-anchor","middle").attr("dominant-baseline","central")
        .attr("fill","#fff").attr("font-size", d => d.risk >= 70 ? "14px" : "12px")
        .attr("font-weight","bold")
        .style("pointer-events","none");

    // ============================================================
    // ПОДПИСИ — поверх всего
    // ============================================================
    const labels = container.append("g").selectAll("text")
        .data(graphData.nodes).enter().append("text")
        .text(d => d.name.length > 22 ? d.name.substring(0,20) + "…" : d.name)
        .attr("fill","#e9ecef")
        .attr("font-size","11px")
        .attr("font-weight","500")
        .attr("font-family","'Courier New', monospace")
        .attr("text-anchor","middle")
        .style("pointer-events","none")
        .style("text-shadow","0 0 6px #000, 0 0 3px #000");

    labels.append("title").text(d => d.name);

    // ============================================================
    // TOOLTIP
    // ============================================================
    const tooltip = d3.select("body").append("div")
        .style("position","absolute").style("display","none")
        .style("background","rgba(13,15,25,0.96)")
        .style("border","1px solid rgba(255,255,255,0.15)")
        .style("border-radius","6px").style("padding","8px 12px")
        .style("font-size","12px").style("color","#e9ecef")
        .style("pointer-events","none").style("z-index","9999")
        .style("box-shadow","0 4px 24px rgba(0,0,0,0.7)");

    // ============================================================
    // ПУТЬ СВЯЗИ (дуга при параллельных рёбрах)
    // ============================================================
    function linkPath(d) {
        const sx = d.source.x, sy = d.source.y;
        const tx = d.target.x, ty = d.target.y;
        const total = d.curve_total || 1;
        const idx   = d.curve_index || 0;
        if (total <= 1) return `M${sx},${sy} L${tx},${ty}`;

        const step  = 32;
        const oi    = Math.ceil(idx/2) * (idx % 2 === 0 ? 1 : -1);
        const idA   = typeof d.source==="object" ? d.source.id : d.source;
        const idB   = typeof d.target==="object" ? d.target.id : d.target;
        let offset  = oi * step * (idA > idB ? -1 : 1);

        const mx = (sx+tx)/2, my = (sy+ty)/2;
        const dx = tx-sx, dy = ty-sy;
        const len = Math.sqrt(dx*dx+dy*dy) || 1;
        return `M${sx},${sy} Q${mx + (-dy/len)*offset},${my + (dx/len)*offset} ${tx},${ty}`;
    }

    // ============================================================
    // СОБЫТИЯ УЗЛОВ — ховер + клик
    // ============================================================
    nodeGroups
        .on("mouseover", function(event, d) {
            // Увеличить этот узел
            d3.select(this).selectAll("circle")
                .transition().duration(120)
                .attr("r", (_, i) => i===0 ? getNodeR(d.risk)+13 : getNodeR(d.risk)+5);

            // Затемнить несвязанные
            const connectedIds = new Set([d.id]);
            graphData.links.forEach(l => {
                const s = typeof l.source==="object"?l.source.id:l.source;
                const t = typeof l.target==="object"?l.target.id:l.target;
                if (s===d.id) connectedIds.add(t);
                if (t===d.id) connectedIds.add(s);
            });
            nodeGroups.attr("opacity", n => connectedIds.has(n.id) ? 1 : 0.1);
            labels.attr("opacity", n => connectedIds.has(n.id) ? 1 : 0.08);
            linkMain.attr("opacity", l => {
                const s = typeof l.source==="object"?l.source.id:l.source;
                const t = typeof l.target==="object"?l.target.id:l.target;
                return (s===d.id||t===d.id) ? 1 : 0.04;
            });
            linkBg.attr("opacity", l => {
                const s = typeof l.source==="object"?l.source.id:l.source;
                const t = typeof l.target==="object"?l.target.id:l.target;
                return (s===d.id||t===d.id) ? 0.28 : 0;
            });

            tooltip.style("display","block")
                .style("left",(event.pageX+14)+"px")
                .style("top",(event.pageY-36)+"px")
                .html(`<strong>${d.name}</strong><br>
                    <span style="color:${getNodeColor(d.risk)}">Риск: ${d.risk}/100</span>`);
        })
        .on("mousemove", function(event) {
            tooltip.style("left",(event.pageX+14)+"px").style("top",(event.pageY-36)+"px");
        })
        .on("mouseout", function(event, d) {
            d3.select(this).selectAll("circle")
                .transition().duration(120)
                .attr("r", (_, i) => i===0 ? getNodeR(d.risk)+7 : getNodeR(d.risk));
            nodeGroups.attr("opacity",1);
            labels.attr("opacity",1);
            linkMain.attr("opacity",0.9);
            linkBg.attr("opacity",0.10);
            tooltip.style("display","none");
        })
        .on("click", (event, d) => {
            event.stopPropagation();
            window.location.href = `${companyUrl}${d.id}/`;
        });

    // ============================================================
    // СОБЫТИЯ СВЯЗЕЙ — ховер
    // ============================================================
    linkMain
        .on("mouseover", function(event, d) {
            d3.select(this).transition().duration(100).attr("stroke-width",5).attr("opacity",1);
            tooltip.style("display","block")
                .style("left",(event.pageX+12)+"px")
                .style("top",(event.pageY-30)+"px")
                .html(`<strong>${LINK_LABELS[d.type]||d.type}</strong>`);
        })
        .on("mousemove", function(event) {
            tooltip.style("left",(event.pageX+12)+"px").style("top",(event.pageY-30)+"px");
        })
        .on("mouseout", function() {
            d3.select(this).transition().duration(100).attr("stroke-width",2.5).attr("opacity",0.9);
            tooltip.style("display","none");
        });

    // ============================================================
    // СИМУЛЯЦИЯ
    // ============================================================
    const simulation = d3.forceSimulation(graphData.nodes)
        .force("link",
            d3.forceLink(graphData.links).id(d=>d.id).distance(220))
        .force("charge", d3.forceManyBody().strength(-1200))
        .force("center",  d3.forceCenter(width/2, height/2))
        .force("collide", d3.forceCollide().radius(88))
        .alphaDecay(0.03);   // медленнее остывает → узлы лучше расходятся

    simulation.on("tick", () => {
        linkMain.attr("d", linkPath);
        linkBg.attr("d",   linkPath);
        nodeGroups.attr("transform", d => `translate(${d.x},${d.y})`);
        labels.attr("x", d => d.x).attr("y", d => d.y + getNodeR(d.risk) + 16);
    });

    // ============================================================
    // DRAG УЗЛОВ
    // ============================================================
    nodeGroups.call(
        d3.drag()
            .filter(event => !event.button)          // только ЛКМ
            .on("start", function(event, d) {
                event.sourceEvent.stopPropagation();  // не захватывать pan
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x; d.fy = d.y;
            })
            .on("drag", function(event, d) {
                d.fx = event.x; d.fy = event.y;
            })
            .on("end", function(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null; d.fy = null;
            })
    );

    // ============================================================
    // ZOOM + PAN (трансформируем ТОЛЬКО container, не весь svg)
    // ============================================================
    const zoom = d3.zoom()
        .scaleExtent([0.2, 4])
        .on("zoom", event => {
            container.attr("transform", event.transform);
        });

    // Применяем zoom на SVG — pan работает по фону, скролл — всегда
    svg.call(zoom)
        .on("dblclick.zoom", null);   // двойной клик не зумит

    // Начальный масштаб: центрируем граф
    svg.call(zoom.transform, d3.zoomIdentity.translate(0, 0).scale(1));

} // end if
