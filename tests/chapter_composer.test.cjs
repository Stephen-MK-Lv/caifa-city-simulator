const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const source = fs.readFileSync(path.join(__dirname, '../app/static/portal.js'), 'utf8');
const composer = {innerHTML: '', querySelectorAll: () => []};
const subjectFilter = {};
const schoolCase = {kind: 'ex3-4', name: '购入教学用具', entities: ['school'], unit: '元', amount: '30000'};
const policeCase = {kind: 'ex10-1', name: '财政直接支付办公用品款', entities: ['police'], unit: '元', amount: '20000'};
const policeUtilities = {kind: 'ex11-6', name: '支付行政活动水费和电费', entities: ['police'], unit: '元', amount: '4350'};
const packages = {
    'chapter-1': [
        {kind: schoolCase.kind, entity: 'school', amount: schoolCase.amount},
        {kind: policeCase.kind, entity: 'police', amount: policeCase.amount},
    ],
    'chapter-2': [{kind: policeUtilities.kind, entity: 'police', amount: policeUtilities.amount}],
};
const chapters = Object.keys(packages).map((id, index) => ({
    chapter: index + 1,
    title: ['中国政府会计理论与制度体系', '中国政府会计改革实践'][index],
    business_kinds: packages[id].map(e => e.kind),
    report_tables: [],
}));
let submitted, submit;
const context = {
    course: {
        chapters,
        entities: {school: '彩珐市职业学校', police: '彩珐市公安局'},
        business_types: [schoolCase, policeCase, policeUtilities],
        profiles: [{id: 'textbook', name: '教材例题'}],
        exercise_templates: Object.keys(packages).map((id, index) => ({
            id, chapter: index + 1, name: '本章全部业务', events: packages[id],
        })),
    },
    dashboard: {classes: [{id: 'class-a', name: '指定班级', profile_id: 'textbook'}]},
    classId: 'class-a',
    selectedChapters: {1: true, 2: true},
    chapterDrafts: {},
    names: {school: '职业学校', police: '公安局'},
    esc: String,
    options: items => items.map(([key, label]) => `<option value="${key}">${label}</option>`).join(''),
    bindForm: (_id, callback) => { submit = callback; },
    requestId: () => 'request-test',
    post: async (url, body) => { submitted = {url, body}; return {assignments: body.tasks}; },
    refresh: async () => {},
    notice: () => {},
};
const packButton = {dataset: {pack: 'chapter-1'}};
const form = {
    elements: Object.fromEntries(['title', 'instruction', 'amount_variation_percent', 'profile_id'].map(k => [k, {}])),
    querySelectorAll: selector => selector === '[data-pack]' ? [packButton] : [],
};
context.$ = id => ({
    '#composer': composer,
    '#assignment-form': form,
    '#assignment-entity-filter': subjectFilter,
}[id] || {});
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf("let assignmentEntityFilter"), source.indexOf("function entriesTable(")), context);
context.chapterDrafts[1] = context.newDraft(1);
context.chapterDrafts[2] = context.newDraft(2);
context.draft = context.chapterDrafts[1];
context.renderComposer();
assert.match(composer.innerHTML, /value="police">彩珐市公安局/);
subjectFilter.onchange({target: {value: 'police'}});
assert.match(composer.innerHTML, /data-kind="ex10-1"/);
assert.doesNotMatch(composer.innerHTML, /data-kind="ex3-4"/);
packButton.onclick();
assert.equal(context.draft.events['ex10-1'].entity, 'police');
assert.equal(context.draft.events['ex3-4'], undefined);
context.draft = context.chapterDrafts[2];
packButton.dataset.pack = 'chapter-2';
context.renderComposer();
packButton.onclick();
assert.match(composer.innerHTML, /所选2章/);

submit().then(() => {
    assert.equal(submitted.url, '/teaching/assignment-batches');
    assert.equal(submitted.body.class_id, 'class-a');
    assert.equal(submitted.body.tasks.length, 2);
    assert.ok(submitted.body.tasks.every(task => task.class_id === 'class-a' && task.events.length === 1));
    assert.deepEqual(Array.from(submitted.body.tasks, task => task.events[0].entity), ['police', 'police']);
    console.log('Police-only selection publishes valid textbook case packs in both selected chapters.');
}).catch(error => {
    console.error(error);
    process.exitCode = 1;
});
