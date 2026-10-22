const {test} = require('node:test');
const assert = require('node:assert/strict');
const {normalize, distance, matchScore} = require('./static/app.js');

test('normalizes surrounding spaces and case', () => {
  assert.equal(normalize('  PICKUP  '), 'pickup');
});
test('matches substrings and empty queries', () => {
  assert.equal(matchScore('toggle switch', 'switch'), 0);
  assert.equal(matchScore('pickup', ''), 0);
});
test('finds similar whole tags, individual words and multiple words', () => {
  for (const [tag, query] of [['humbucker', 'humbuker'], ['pickup', 'pckup'],
    ['toggle switch', 'swich'], ['push pull switch', 'psh swich']]) {
    assert.ok(Number.isFinite(matchScore(tag, query)), `${tag}: ${query}`);
    assert.ok(matchScore(tag, query) > 0);
  }
});
test('ranks exact matches first and excludes unrelated tags', () => {
  assert.ok(matchScore('pickup', 'pickup') < matchScore('pickup', 'pckup'));
  assert.equal(matchScore('resistor', 'humbucker'), Infinity);
  assert.equal(distance('pickup', 'pckup'), 1);
});
