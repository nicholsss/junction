/* The human decision contract, shared by the walkthrough and the CLI tests.
 *
 * Pure: no DOM, no network, no storage. engine/decision.py implements the same
 * rules. engine/decision-contract-cases.json is executed by both.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.DecisionContract = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var ACTIONS = ['accept', 'changes', 'escalate'];
  var FINDING_POSITIONS = ['accept_scope', 'change_required', 'needs_owner'];
  var EFFECTS = ['accept_compatible', 'changes_required', 'escalation_required'];

  // Only the templates this project renders count as placeholders. A broad
  // bracket test would reject legitimate bracketed domain text.
  var PLACEHOLDERS = [
    '[your answer]', '[your reason]', '[reason]', '[choose a position]',
    '[choose your position]', '[your reason and residual risk]',
    '[reason, including residual risk]', '[refusal position]',
    '[finding position]', '[acknowledge]'
  ];
  var BRACKET_ONLY = /^\s*\[[^\]]*\]\s*$/;

  function error(code, message) { return { code: code, message: message }; }

  function isPlaceholder(text) {
    var lowered = String(text == null ? '' : text).trim().toLowerCase();
    if (BRACKET_ONLY.test(String(text))) return true;
    for (var i = 0; i < PLACEHOLDERS.length; i++) {
      if (lowered.indexOf(PLACEHOLDERS[i]) >= 0) return true;
    }
    return false;
  }

  function validateDecision(action, reason, refusalPositions, findingPositions,
                            acknowledgedUnknowns, contract) {
    var errors = [];
    contract = contract || {};
    if (ACTIONS.indexOf(action) < 0) {
      return [error('outcome_invalid', 'Outcome must be accept, changes or escalate.')];
    }
    reason = typeof reason === 'string' ? reason : '';
    if (!reason.trim()) {
      errors.push(error('reason_missing', 'A non-empty human reason is required.'));
    } else if (isPlaceholder(reason)) {
      errors.push(error('reason_placeholder',
        'Replace the template placeholder in the reason with your own words.'));
    }

    var refusals = {};
    (contract.refusals || []).forEach(function (item) { refusals[item.id] = item; });
    var findings = contract.findings || [];
    var unknowns = contract.unknowns || [];
    var seenRefusals = {}, seenFindings = {}, seenUnknowns = {};

    (refusalPositions || []).forEach(function (entry) {
      var id = entry && (entry.refusalId || entry.id);
      var position = entry && (entry.positionId || entry.position);
      if (!Object.prototype.hasOwnProperty.call(refusals, id)) {
        errors.push(error('refusal_unknown', (id || '?') + ': not a refusal in this receipt.'));
        return;
      }
      if (seenRefusals[id]) {
        errors.push(error('refusal_duplicate', id + ': a position was given more than once.'));
        return;
      }
      seenRefusals[id] = true;
      var options = {};
      (refusals[id].positions || []).forEach(function (p) { options[p.id] = p; });
      var option = options[position];
      if (!option) {
        var allowed = Object.keys(options).join(', ') || 'none recorded';
        errors.push(error('refusal_position_unknown',
          id + ": '" + position + "' is not a recorded position. Choose one of: " + allowed + '.'));
        return;
      }
      if (action === 'accept' && option.effect !== 'accept_compatible') {
        errors.push(error('refusal_position_incompatible',
          id + ": '" + position + "' does not permit acceptance; it requires " +
          String(option.effect).replace(/_/g, ' ') + '.'));
      }
    });

    (findingPositions || []).forEach(function (entry) {
      var id = entry && (entry.findingId || entry.id);
      var position = entry && (entry.positionId || entry.position);
      if (findings.indexOf(id) < 0) {
        errors.push(error('finding_unknown',
          (id || '?') + ': not an outside-requirement item in this receipt.'));
        return;
      }
      if (seenFindings[id]) {
        errors.push(error('finding_duplicate', id + ': a position was given more than once.'));
        return;
      }
      seenFindings[id] = true;
      if (FINDING_POSITIONS.indexOf(position) < 0) {
        errors.push(error('finding_position_unknown',
          id + ": '" + position + "' is not a recorded finding position. Choose one of: " +
          FINDING_POSITIONS.join(', ') + '.'));
        return;
      }
      if (action === 'accept' && position !== 'accept_scope') {
        errors.push(error('finding_position_incompatible',
          id + ": '" + position + "' does not permit acceptance; choose accept_scope."));
      }
    });

    (acknowledgedUnknowns || []).forEach(function (id) {
      if (unknowns.indexOf(id) < 0) {
        errors.push(error('unknown_unknown', (id || '?') + ': not an unknown in this receipt.'));
        return;
      }
      if (seenUnknowns[id]) {
        errors.push(error('unknown_duplicate', id + ': acknowledged more than once.'));
        return;
      }
      seenUnknowns[id] = true;
    });

    if (action === 'accept') {
      Object.keys(refusals).forEach(function (id) {
        if (!seenRefusals[id]) {
          errors.push(error('refusal_position_missing', id + ': a position is required to accept.'));
        }
      });
      findings.forEach(function (id) {
        if (!seenFindings[id]) {
          errors.push(error('finding_position_missing', id + ': a position is required to accept.'));
        }
      });
      unknowns.forEach(function (id) {
        if (!seenUnknowns[id]) {
          errors.push(error('unknown_missing', id + ': acknowledge this residual unknown to accept.'));
        }
      });
    }
    return errors;
  }

  return {
    ACTIONS: ACTIONS,
    FINDING_POSITIONS: FINDING_POSITIONS,
    EFFECTS: EFFECTS,
    validateDecision: validateDecision,
    isPlaceholder: isPlaceholder
  };
});
