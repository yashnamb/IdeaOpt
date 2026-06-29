"""Live HTML visualizer for exploration runs."""

from __future__ import annotations

from string import Template

from ideaopt.models import ReportState

_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
$AUTO_REFRESH
<title>$TITLE</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; }
.header { background: #1a1a2e; color: #fff; padding: 24px 32px; }
.header h1 { font-size: 22px; margin-bottom: 8px; }
.header .idea { font-size: 15px; opacity: 0.85; margin-bottom: 12px; }
.header .meta { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.badge-running { background: #22c55e; color: #fff; animation: pulse 1.5s ease-in-out infinite; }
.badge-complete { background: #3b82f6; color: #fff; }
.badge-score { background: #f59e0b; color: #1a1a2e; font-size: 18px; padding: 6px 16px; border-radius: 16px; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
.grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
@media (min-width: 768px) { .grid-2 { grid-template-columns: 1fr 1fr; } }
.card { background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 20px; }
.card h2 { font-size: 16px; color: #1a1a2e; margin-bottom: 14px; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }
.card.waiting { opacity: 0.4; }
.card.waiting .placeholder { text-align: center; color: #999; padding: 24px 0; font-style: italic; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 8px 12px; border-bottom: 1px solid #e5e7eb; }
th { font-weight: 600; color: #555; }
.changed { background: #fef3c7; }
.timeline-row { display: flex; align-items: center; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
.timeline-step { padding: 6px 12px; border-radius: 6px; font-size: 13px; background: #e5e7eb; color: #555; }
.timeline-step.active { background: #1a1a2e; color: #fff; }
.timeline-arrow { color: #999; font-size: 16px; }
.progress-bar-container { margin-bottom: 10px; }
.progress-label { display: flex; justify-content: space-between; font-size: 13px; margin-bottom: 3px; }
.progress-track { height: 18px; background: #e5e7eb; border-radius: 9px; overflow: hidden; }
.progress-fill { height: 100%; border-radius: 9px; transition: width 0.3s; }
.score-green { background: #22c55e; }
.score-yellow { background: #f59e0b; }
.score-red { background: #ef4444; }
.formula { font-family: 'Courier New', monospace; background: #f8f9fa; padding: 12px; border-radius: 6px; font-size: 14px; margin: 10px 0; }
.rejected-table { font-size: 13px; }
.chart-wrapper { position: relative; max-width: 500px; margin: 0 auto; }
</style>
</head>
<body>
<div id="app"></div>
<script>
var STATE = $REPORT_JSON;

function scoreColor(v) {
    if (v >= 7) return 'score-green';
    if (v >= 5) return 'score-yellow';
    return 'score-red';
}

function el(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) { for (var k in attrs) { if (k === 'className') e.className = attrs[k]; else if (k === 'innerHTML') e.innerHTML = attrs[k]; else e.setAttribute(k, attrs[k]); } }
    if (typeof children === 'string') e.innerHTML = children;
    else if (Array.isArray(children)) children.forEach(function(c) { if (c) e.appendChild(c); });
    return e;
}

function renderHeader(app, s) {
    var header = el('div', {className: 'header'});
    header.appendChild(el('h1', {}, 'IdeaOpt Design Space Report'));
    header.appendChild(el('div', {className: 'idea'}, escapeHtml(s.original_idea)));
    var meta = el('div', {className: 'meta'});
    var isComplete = s.status === 'complete';
    var badgeClass = isComplete ? 'badge badge-complete' : 'badge badge-running';
    var badgeText = isComplete ? 'Complete' : capitalizeFirst(s.status) + '...';
    meta.appendChild(el('span', {className: badgeClass}, badgeText));
    if (s.budget_summary) {
        meta.appendChild(el('span', {className: 'badge'}, s.budget_summary.total_calls + ' calls'));
        meta.appendChild(el('span', {className: 'badge'}, s.budget_summary.total_duration.toFixed(1) + 's'));
    }
    if (isComplete && s.best_candidate) {
        meta.appendChild(el('span', {className: 'badge badge-score'}, 'Score: ' + s.best_candidate.final_score.toFixed(2)));
    }
    header.appendChild(meta);
    app.appendChild(header);
}

function renderDesignPoint(app, s) {
    var card = el('div', {className: 'card'});
    card.appendChild(el('h2', {id: 'section-design-point'}, 'Design Point'));
    if (!s.design_point) {
        card.className = 'card waiting';
        card.appendChild(el('div', {className: 'placeholder'}, 'Waiting for data...'));
        app.querySelector('.container .grid').appendChild(card);
        return;
    }
    var fields = ['customer','problem','solution','value_prop','wedge','business_model','gtm_path'];
    var labels = ['Customer','Problem','Solution','Value Prop','Wedge','Business Model','GTM Path'];
    var html = '<table><tbody>';
    for (var i = 0; i < fields.length; i++) {
        html = html + '<tr><th>' + labels[i] + '</th><td>' + escapeHtml(s.design_point[fields[i]]) + '</td></tr>';
    }
    html = html + '</tbody></table>';
    card.appendChild(el('div', {innerHTML: html}));
    app.querySelector('.container .grid').appendChild(card);
}

function renderTimeline(app, s) {
    var card = el('div', {className: 'card'});
    card.appendChild(el('h2', {id: 'section-timeline'}, 'Iteration Timeline'));
    var hasData = s.iterations.length > 0 || s.current_candidates.length > 0;
    if (!hasData) {
        card.className = 'card waiting';
        card.appendChild(el('div', {className: 'placeholder'}, 'Waiting for data...'));
        app.querySelector('.container .grid').appendChild(card);
        return;
    }
    var wrapper = el('div', {});
    var allIters = s.iterations.slice();
    if (s.current_candidates.length > 0 && (allIters.length === 0 || s.current_iteration > allIters[allIters.length - 1].iteration)) {
        var inProgress = {iteration: s.current_iteration, candidates: s.current_candidates, scored_candidates: s.current_scored, merged_candidate: null, in_progress: true};
        allIters.push(inProgress);
    }
    for (var i = 0; i < allIters.length; i++) {
        var it = allIters[i];
        var row = el('div', {className: 'timeline-row'});
        row.appendChild(el('strong', {}, 'Iter ' + it.iteration + ': '));
        var genClass = 'timeline-step' + (it.candidates.length > 0 ? ' active' : '');
        row.appendChild(el('span', {className: genClass}, 'Generated(' + it.candidates.length + ')'));
        row.appendChild(el('span', {className: 'timeline-arrow'}, ' &rarr; '));
        var scored = it.scored_candidates || [];
        var scoredClass = 'timeline-step' + (scored.length > 0 ? ' active' : '');
        row.appendChild(el('span', {className: scoredClass}, 'Scored(' + scored.length + ')'));
        row.appendChild(el('span', {className: 'timeline-arrow'}, ' &rarr; '));
        var bestScore = scored.length > 0 ? Math.max.apply(null, scored.map(function(sc) { return sc.final_score; })).toFixed(2) : '-';
        var bestClass = 'timeline-step' + (scored.length > 0 ? ' active' : '');
        row.appendChild(el('span', {className: bestClass}, 'Best(' + bestScore + ')'));
        row.appendChild(el('span', {className: 'timeline-arrow'}, ' &rarr; '));
        var merged = it.merged_candidate != null;
        var mergedLabel = merged ? '&#10003;' : '&#10007;';
        var mergedClass = 'timeline-step' + (merged ? ' active' : '');
        row.appendChild(el('span', {className: mergedClass}, 'Merged(' + mergedLabel + ')'));
        wrapper.appendChild(row);
    }
    card.appendChild(wrapper);
    app.querySelector('.container .grid').appendChild(card);
}

function renderRadar(app, s) {
    var card = el('div', {className: 'card'});
    card.appendChild(el('h2', {id: 'section-radar'}, 'Candidate Comparison'));
    var scored = s.current_scored.length > 0 ? s.current_scored : [];
    if (scored.length === 0) {
        for (var ii = 0; ii < s.iterations.length; ii++) {
            scored = scored.concat(s.iterations[ii].scored_candidates);
        }
    }
    if (scored.length === 0) {
        card.className = 'card waiting';
        card.appendChild(el('div', {className: 'placeholder'}, 'Waiting for data...'));
        app.querySelector('.container .grid').appendChild(card);
        return;
    }
    scored.sort(function(a, b) { return b.final_score - a.final_score; });
    var top = scored.slice(0, 5);
    var chartWrap = el('div', {className: 'chart-wrapper'});
    var canvas = el('canvas', {id: 'radarChart'});
    chartWrap.appendChild(canvas);
    card.appendChild(chartWrap);
    app.querySelector('.container .grid').appendChild(card);
    var colors = ['rgba(59,130,246,','rgba(239,68,68,','rgba(34,197,94,','rgba(249,115,22,','rgba(168,85,247,'];
    var datasets = [];
    for (var i = 0; i < top.length; i++) {
        var sc = top[i];
        var c = colors[i % colors.length];
        var bw = i === 0 ? 3 : 1.5;
        var bg = i === 0 ? c + '0.25)' : c + '0.1)';
        datasets.push({
            label: sc.candidate.summary.substring(0, 30),
            data: [sc.eval_scores.pain, sc.eval_scores.specificity, sc.eval_scores.differentiation, sc.eval_scores.testability, sc.eval_scores.feasibility],
            borderColor: c + '1)',
            backgroundColor: bg,
            borderWidth: bw,
            pointRadius: 3
        });
    }
    new Chart(canvas, {
        type: 'radar',
        data: { labels: ['Pain','Specificity','Differentiation','Testability','Feasibility'], datasets: datasets },
        options: { scales: { r: { beginAtZero: true, max: 10 } }, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } }
    });
}

function renderProgression(app, s) {
    var card = el('div', {className: 'card'});
    card.appendChild(el('h2', {id: 'section-progression'}, 'Score Progression'));
    if (s.iterations.length === 0) {
        card.className = 'card waiting';
        card.appendChild(el('div', {className: 'placeholder'}, 'Waiting for data...'));
        app.querySelector('.container .grid').appendChild(card);
        return;
    }
    var chartWrap = el('div', {className: 'chart-wrapper'});
    var canvas = el('canvas', {id: 'progressionChart'});
    chartWrap.appendChild(canvas);
    card.appendChild(chartWrap);
    app.querySelector('.container .grid').appendChild(card);
    var labels = [];
    var composite = [];
    var drift = [];
    var complexity = [];
    var finalScores = [];
    for (var i = 0; i < s.iterations.length; i++) {
        var it = s.iterations[i];
        labels.push('Iter ' + it.iteration);
        var best = it.scored_candidates.slice().sort(function(a, b) { return b.final_score - a.final_score; })[0];
        if (best) {
            composite.push(best.composite_score);
            drift.push(best.drift_score);
            complexity.push(best.complexity_score);
            finalScores.push(best.final_score);
        } else {
            composite.push(0);
            drift.push(0);
            complexity.push(0);
            finalScores.push(0);
        }
    }
    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'Composite', data: composite, backgroundColor: 'rgba(59,130,246,0.7)' },
                { label: 'Drift', data: drift, backgroundColor: 'rgba(249,115,22,0.7)' },
                { label: 'Complexity', data: complexity, backgroundColor: 'rgba(168,85,247,0.7)' },
                { type: 'line', label: 'Final', data: finalScores, borderColor: '#22c55e', backgroundColor: 'transparent', borderWidth: 2, pointRadius: 4, tension: 0.2 }
            ]
        },
        options: { scales: { y: { beginAtZero: true } }, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } }
    });
}

function renderEvolution(app, s) {
    var card = el('div', {className: 'card'});
    card.appendChild(el('h2', {id: 'section-evolution'}, 'Design Point Evolution'));
    if (!s.design_point || !s.best_candidate) {
        card.className = 'card waiting';
        card.appendChild(el('div', {className: 'placeholder'}, 'Waiting for data...'));
        app.querySelector('.container .grid').appendChild(card);
        return;
    }
    var fields = ['customer','problem','solution','value_prop','wedge','business_model','gtm_path'];
    var labels = ['Customer','Problem','Solution','Value Prop','Wedge','Business Model','GTM Path'];
    var orig = s.design_point;
    var best = s.best_candidate.candidate.design_point;
    var html = '<table><thead><tr><th>Dimension</th><th>Original</th><th>Best Candidate</th></tr></thead><tbody>';
    for (var i = 0; i < fields.length; i++) {
        var f = fields[i];
        var changed = orig[f] !== best[f];
        var cls = changed ? ' class="changed"' : '';
        html = html + '<tr' + cls + '><th>' + labels[i] + '</th><td>' + escapeHtml(orig[f]) + '</td><td>' + escapeHtml(best[f]) + '</td></tr>';
    }
    html = html + '</tbody></table>';
    card.appendChild(el('div', {innerHTML: html}));
    app.querySelector('.container .grid').appendChild(card);
}

function renderResults(app, s) {
    var card = el('div', {className: 'card'});
    card.appendChild(el('h2', {id: 'section-results'}, 'Score Breakdown &amp; Results'));
    if (s.status !== 'complete' || !s.best_candidate) {
        card.className = 'card waiting';
        card.appendChild(el('div', {className: 'placeholder'}, 'Waiting for data...'));
        app.querySelector('.container .grid').appendChild(card);
        return;
    }
    var bc = s.best_candidate;
    var es = bc.eval_scores;
    var axes = [['Pain', es.pain], ['Specificity', es.specificity], ['Differentiation', es.differentiation], ['Testability', es.testability], ['Feasibility', es.feasibility]];
    var barsHtml = '';
    for (var i = 0; i < axes.length; i++) {
        var name = axes[i][0];
        var val = axes[i][1];
        var pct = (val / 10 * 100).toFixed(0);
        var cls = scoreColor(val);
        barsHtml = barsHtml + '<div class="progress-bar-container"><div class="progress-label"><span>' + name + '</span><span>' + val.toFixed(1) + '/10</span></div><div class="progress-track"><div class="progress-fill ' + cls + '" style="width:' + pct + '%"></div></div></div>';
    }
    card.appendChild(el('div', {innerHTML: barsHtml}));
    var formula = 'S(x) = ' + bc.composite_score.toFixed(2) + ' - ' + bc.drift_score.toFixed(2) + '*D - ' + bc.complexity_score.toFixed(2) + '*C = ' + bc.final_score.toFixed(2);
    card.appendChild(el('div', {className: 'formula'}, formula));
    if (s.validation_experiment) {
        card.appendChild(el('h3', {}, 'Validation Experiment'));
        card.appendChild(el('p', {}, escapeHtml(s.validation_experiment)));
    }
    var allScored = [];
    for (var j = 0; j < s.iterations.length; j++) {
        allScored = allScored.concat(s.iterations[j].scored_candidates);
    }
    var rejected = allScored.filter(function(sc) { return sc.candidate.summary !== bc.candidate.summary; });
    rejected.sort(function(a, b) { return b.final_score - a.final_score; });
    if (rejected.length > 0) {
        var thtml = '<h3>Rejected Candidates</h3><table class="rejected-table"><thead><tr><th>Summary</th><th>Final</th><th>Weakest Axis</th><th>Score</th></tr></thead><tbody>';
        for (var k = 0; k < rejected.length; k++) {
            var r = rejected[k];
            var re = r.eval_scores;
            var axisScores = {Pain: re.pain, Specificity: re.specificity, Differentiation: re.differentiation, Testability: re.testability, Feasibility: re.feasibility};
            var weakest = 'Pain';
            var weakVal = re.pain;
            for (var ax in axisScores) { if (axisScores[ax] < weakVal) { weakest = ax; weakVal = axisScores[ax]; } }
            thtml = thtml + '<tr><td>' + escapeHtml(r.candidate.summary) + '</td><td>' + r.final_score.toFixed(2) + '</td><td>' + weakest + '</td><td>' + weakVal.toFixed(1) + '</td></tr>';
        }
        thtml = thtml + '</tbody></table>';
        card.appendChild(el('div', {innerHTML: thtml}));
    }
    app.querySelector('.container .grid').appendChild(card);
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

document.addEventListener('DOMContentLoaded', function() {
    var app = document.getElementById('app');
    renderHeader(app, STATE);
    var container = el('div', {className: 'container'});
    var grid = el('div', {className: 'grid'});
    container.appendChild(grid);
    app.appendChild(container);
    renderDesignPoint(app, STATE);
    renderTimeline(app, STATE);
    renderRadar(app, STATE);
    renderProgression(app, STATE);
    renderEvolution(app, STATE);
    renderResults(app, STATE);
});
</script>
</body>
</html>
""")


def generate_html(state: ReportState) -> str:
    state_json = state.model_dump_json()
    safe_json = state_json.replace("</script>", r"<\/script>")

    auto_refresh = ""
    if state.status != "complete":
        auto_refresh = '<meta http-equiv="refresh" content="3">'

    title = "IdeaOpt Report"

    return _TEMPLATE.substitute(
        REPORT_JSON=safe_json,
        TITLE=title,
        AUTO_REFRESH=auto_refresh,
    )
