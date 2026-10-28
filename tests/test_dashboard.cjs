// Gedrag van het resultatenoverzicht, zonder extra npm-pakketten.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    hidden: false, value: '', textContent: '', open: false, dataset: {},
    classList: { add() {}, remove() {} }, addEventListener() {},
    querySelectorAll() { return []; },
    get innerHTML() { return this.html || ''; },
    set innerHTML(value) { this.html = value; this.writes = (this.writes || 0) + 1; },
  });
  return elements.get(id);
}
let responses = {};
const document = { getElementById: element, addEventListener() {}, hidden: false };
const sandbox = {
  document, location: { search: '', protocol: 'http:' }, URLSearchParams,
  AbortController, setTimeout, clearTimeout, setInterval() {},
  fetch: async url => ({ ok: true, json: async () => responses[url] }),
};
vm.createContext(sandbox);
let code = fs.readFileSync('app/index.html', 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
code = code.replace('  loadCatalog(true);\n  setInterval', '  setInterval');
code = code.replace('})();', 'globalThis.test = { datasets, render, loadCatalog, get selected() {return selected;}, select(value) {selected=value;} };})();');
vm.runInContext(code, sandbox);
const api = sandbox.test;

const round = (date, room, rssi) => ({
  gestart_op_utc: date, verwacht_ssid: 'Voorbeeld',
  metingen: [{ kamer: room, rssi_dbm: rssi }],
});
async function main() {
  responses = {
    './api/catalog': [
      { name: 'oud.json', revision: '1000000-1' },
      { name: 'nieuw.json', revision: '2000000-1' },
    ],
    './oud.json': round('2026-01-01', 'Oude kamer', -51),
    './nieuw.json': round('2026-02-01', '<Nieuwe kamer>', null),
  };
  await api.loadCatalog();
  assert.equal(api.selected, 'nieuw.json', 'Open de nieuwste ronde, nooit direct de vergelijking');
  assert.match(element('app').innerHTML, /&lt;Nieuwe kamer&gt;/, 'Escape kamernamen');
  assert.match(element('app').innerHTML, /Nog onbekend/, 'Ontbrekend signaal is niet goed');
  assert.match(element('app').innerHTML, /<details class="disclosure"/, 'Verberg de technische analyse');
  assert.doesNotMatch(element('app').innerHTML, /disclosure" open/);
  const writes = element('app').writes;
  await api.loadCatalog();
  assert.equal(element('app').writes, writes, 'Teken ongewijzigde resultaten niet opnieuw');

  api.select('oud.json');
  api.render();
  responses['./api/catalog'][1].revision = '3000000-1';
  responses['./nieuw.json'].metingen.push({kamer: 'Werkkamer', rssi_dbm: -80});
  await api.loadCatalog();
  assert.equal(api.selected, 'oud.json', 'Behoud een bewust gekozen eerdere ronde');

  api.select('nieuw.json');
  responses['./api/catalog'][0].revision = '4000000-1';
  await api.loadCatalog();
  assert.equal(api.selected, 'oud.json', 'Toon een hervatte ronde als laatst bijgewerkt');

  api.select('__ALL__');
  api.render();
  assert.match(element('app').innerHTML, /Vergelijking per kamer/);
  console.log('Resultatenflow OK: nieuwste ronde, onbekende waarden, escaping, automatische updates en vergelijken.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
