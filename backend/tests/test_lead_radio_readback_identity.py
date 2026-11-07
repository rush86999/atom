"""A known committed message id survives a failed independent readback."""
import asyncio
from tests.test_oracle_radio_send import env, _oracle_on, _reset_radio_server, _seed_thread, _message_rows, _send_args, _context


def test_committed_message_identity_survives_readback_timeout(env, monkeypatch):
    from core.agent_radio import radio_mutations
    _seed_thread(env)
    def fail_read(*args):
        raise TimeoutError('controlled readback unavailable')
    monkeypatch.setattr(radio_mutations, 'read_message', fail_read)
    result = asyncio.run(radio_mutations.send_message(
        _send_args('lead-known-message'), _context('lead-known-message')))
    rows = _message_rows(env)
    assert len(rows) == 1
    assert result['status'] == 'uncertain'
    assert result['remote_id'] == rows[0].id, 'known committed identity was discarded'
    assert result['provider_receipt']['remote_id'] == rows[0].id
