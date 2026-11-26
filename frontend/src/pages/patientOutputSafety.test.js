import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { describe, it } from 'node:test';

const prohibitedPatientTerms = /\b(medication|medicine|drug|dose|prescription|diagnos(?:is|e|ed)|diagnostic|treatment)\b/i;

function source(name) {
  return readFileSync(new URL(name, import.meta.url), 'utf8');
}

describe('patient-facing output safety', () => {
  it('keeps treatment content out of the recommendations page', () => {
    assert.doesNotMatch(source('./Recommendations.jsx'), prohibitedPatientTerms);
  });

  it('does not prompt patients to put treatment details in reading notes', () => {
    assert.doesNotMatch(source('./LogReading.jsx'), prohibitedPatientTerms);
  });

  it('renders the server message without adding treatment content', () => {
    const card = source('../components/RecommendationCard.jsx');
    assert.match(card, /rec\.message/);
    assert.doesNotMatch(card, prohibitedPatientTerms);
  });

  it('keeps very-high urgent wording tied to the saved reading when refresh fails', () => {
    const logPage = source('./LogReading.jsx');
    const recommendations = source('./Recommendations.jsx');
    assert.match(logPage, /veryHighSafetyMessage\(created\.systolic, created\.diastolic\)/);
    assert.match(logPage, /urgentReading/);
    assert.match(recommendations, /urgentReading/);
    assert.match(recommendations, /veryHighSafetyMessage/);
  });
});
