const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Minimal DOM adapter runs the real UI handlers without browser dependencies.
class Element {
  constructor() {
    this.value = '';
    this.textContent = '';
    this.children = [];
    this.events = {};
    this.classList = {toggle() {}};
  }
  addEventListener(name, handler) { this.events[name] = handler; }
  dispatch(name) { return this.events[name]({preventDefault() {}}); }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute() {}
  focus() {}
  reset() {}
}

test('live search adds unique normalized tags and preserves editing and saving', async () => {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  let posted;
  const context = {
    document: {getElementById: get, createElement: () => new Element()},
    window: {addEventListener() {}},
    fetch: async (_, options) => {
      if (options) posted = JSON.parse(options.body);
      return {ok: true, json: async () => ({tags: posted ? posted.tags : ['pickup', 'humbucker'], revision: 'test', normalized: false})};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/app.js'), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  const search = value => { get('search').value = value; get('search').dispatch('input'); };
  const visible = () => get('tags').children.map(row => row.children[0].textContent);

  assert.equal(get('add-tag').disabled, true);
  search('humbuker');
  assert.deepEqual(visible(), ['humbucker']);
  assert.equal(get('add-tag').disabled, false); // Similar is not identical.
  search('  PICKUP  ');
  assert.deepEqual(visible(), ['pickup']);
  assert.equal(get('add-tag').disabled, true);
  get('search-form').dispatch('submit'); // Enter cannot bypass duplicate checks.
  search('');
  assert.equal(visible().length, 2);
  search('  New Tag  ');
  get('search-form').dispatch('submit');
  assert.deepEqual(visible(), ['new tag']);
  assert.equal(get('add-tag').disabled, true);
  get('search-form').dispatch('submit');
  search('');
  assert.deepEqual(visible(), ['pickup', 'humbucker', 'new tag']);
  assert.equal(get('add-tag').disabled, true);

  get('tags').children[2].children[1].children[0].dispatch('click');
  assert.equal(get('edit-section').hidden, false);
  get('tag').value = ' Renamed Tag ';
  get('editor').dispatch('submit');
  assert.equal(get('edit-section').hidden, true);
  assert.deepEqual(visible(), ['pickup', 'humbucker', 'renamed tag']);
  get('tags').children[2].children[1].children[1].dispatch('click');
  assert.deepEqual(visible(), ['pickup', 'humbucker']);
  await get('save').dispatch('click');
  assert.deepEqual(posted.tags, ['pickup', 'humbucker']);
  assert.equal(get('save').disabled, true);
});

test('rebuild button shows progress, counts and errors without changing pending tags', async () => {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  let complete, calls = 0;
  const context = {
    document: {getElementById: get, createElement: () => new Element()},
    window: {addEventListener() {}},
    fetch: async (url, options) => {
      if (url === '/api/indexes') {
        calls++;
        assert.equal(options.method, 'POST');
        assert.equal(options.body, '{}');
        return new Promise(resolve => { complete = resolve; });
      }
      return {ok: true, json: async () => ({tags: ['pickup'], revision: 'test', normalized: false})};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'static/app.js'), 'utf8'), context);
  await new Promise(resolve => setImmediate(resolve));
  get('search').value = 'new tag';
  get('search-form').dispatch('submit');
  assert.equal(get('save').disabled, false);
  const rebuilding = get('build-indexes').dispatch('click');
  assert.equal(get('build-indexes').disabled, true);
  assert.equal(get('index-status').textContent, 'Rebuilding catalog indexes…');
  await get('build-indexes').dispatch('click');
  assert.equal(calls, 1);
  complete({ok: true, json: async () => ({parts: 4, schemes: 2})});
  await rebuilding;
  assert.equal(get('index-status').textContent, 'Indexes rebuilt: 4 parts, 2 schemes.');
  assert.equal(get('build-indexes').disabled, false);
  assert.equal(get('save').disabled, false);
  assert.equal(get('status').textContent, 'You have unsaved changes.');
  assert.equal(get('tags').children[0].children[0].textContent, 'new tag');

  const retry = get('build-indexes').dispatch('click');
  complete({ok: false, json: async () => ({error: 'Invalid scheme metadata'})});
  await retry;
  assert.equal(get('index-status').textContent, 'Invalid scheme metadata');
  assert.equal(get('build-indexes').disabled, false);
});
