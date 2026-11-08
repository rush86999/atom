"""Root internal integrity controls; these are not a public exploit claim."""
import copy
import pytest
from core.task_lifecycle import _supersede_gap_settlement_operations


def _material():
    q = {'question_id': 'question-01', 'status': 'open',
         'source_operation': 'operation-01'}
    before = {'unresolved': [q]}
    after_q = dict(q, status='resolved', resolution_value='authorized answer')
    after = {'unresolved': [after_q]}
    op = {'operation_id': 'operation-01', 'assignment_id': 'assignment-01',
          'step_id': 'step-01', 'status': 'waiting'}
    assignment = {'assignment_id': 'assignment-01', 'steps': [
        {'step_id': 'step-01', 'gap_ids': ['question-01']} ]}
    transition = {'kind': 'record_unresolved', 'resolutions': [
        {'question_id': 'question-01', 'value': 'authorized answer',
         'resolution': 'authorized answer [by reviewer]'}],
        'supersede_operations': ['operation-01']}
    return before, after, op, assignment, transition


def test_exact_open_to_resolved_question_supersedes_only_its_wait():
    before, after, op, assignment, transition = _material()
    result = _supersede_gap_settlement_operations(
        after, [op], assignment, transition, previous_task=before)
    assert result[0]['status'] == 'superseded'
    assert op['status'] == 'waiting', 'source snapshot is immutable'


@pytest.mark.parametrize('case', [
    'missing_question', 'still_open', 'already_resolved', 'missing_previous',
    'different_answer', 'other_operation', 'other_assignment', 'other_step',
    'already_applied', 'different_transition_kind',
])
def test_requested_resolution_is_not_operation_settlement_authority(case):
    before, after, op, assignment, transition = _material()
    if case == 'missing_question': after['unresolved'] = []
    elif case == 'still_open': after['unresolved'][0]['status'] = 'open'
    elif case == 'already_resolved': before['unresolved'][0]['status'] = 'resolved'
    elif case == 'missing_previous': before = None
    elif case == 'different_answer': after['unresolved'][0]['resolution_value'] = 'other'
    elif case == 'other_operation': before['unresolved'][0]['source_operation'] = 'peer-op'
    elif case == 'other_assignment': op['assignment_id'] = 'peer-assignment'
    elif case == 'other_step': op['step_id'] = 'peer-step'
    elif case == 'already_applied': op['status'] = 'applied'
    elif case == 'different_transition_kind': transition['kind'] = 'retain'
    snapshot = copy.deepcopy(op)
    result = _supersede_gap_settlement_operations(
        after, [op], assignment, transition, previous_task=before)
    assert result == [snapshot]
    assert op == snapshot
