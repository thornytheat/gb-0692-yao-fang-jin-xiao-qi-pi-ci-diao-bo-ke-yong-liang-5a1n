import sqlite3
from datetime import datetime, timedelta, timezone
from app.config import COUNTERSIGN_GRACE_HOURS
from app.errors import DomainError
from app.release_store import db, get_order, row_to_order, find_replay, apply_transition, append_ledger
ACTIONS=('首签通过','首签驳回','补签通过','补签驳回','撤回首签','撤回补签')
TRANSITIONS={
 ('待首签','首签通过'):'待补签',
 ('待首签','首签驳回'):'被拦下',
 ('待补签','补签通过'):'已放行',
 ('待补签','补签驳回'):'被拦下',
 ('待补签','撤回首签'):'被拦下',
 ('已放行','撤回首签'):'被拦下',
 ('已放行','撤回补签'):'待补签',
}
def moment(text=None):
    if text is None: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    try: parsed=datetime.fromisoformat(str(text).replace('Z','+00:00'))
    except ValueError: raise DomainError('DATE','时间格式无效')
    if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.replace(microsecond=0).isoformat()
def sign(run_id,order_id,action,pharmacist,action_id,version,at=None):
    if action not in ACTIONS: raise DomainError('ACTION','签核动作无效')
    pharmacist=(pharmacist or '').strip()
    if not pharmacist: raise DomainError('PHARMACIST','必须登记当班药师')
    action_id=(action_id or '').strip()
    if not action_id: raise DomainError('IDEMPOTENT','缺少幂等键')
    if len(action_id)>100 or len(pharmacist)>50: raise DomainError('LIMIT','字段过长')
    at=moment(at)
    try:
        with db() as conn:
            replay=find_replay(conn,action_id)
            if replay: return {'order':row_to_order(get_order(conn,replay['order_id'])),'replayed':True}
            order=get_order(conn,order_id)
            if order is None or order['run_id']!=run_id: raise DomainError('NOT_FOUND','调拨单不存在',404)
            if order['version']!=version: raise DomainError('VERSION','放行结论已变化，请重新载入',409)
            key=(order['state'],action)
            if key not in TRANSITIONS: raise DomainError('STATE',f"当前状态「{order['state']}」不允许「{action}」",409)
            if action.startswith('补签') and pharmacist==order['first_signer']:
                raise DomainError('DUAL','同一名药师不能顶两次签')
            if action=='撤回首签' and pharmacist!=order['first_signer']:
                raise DomainError('WITHDRAW','只能由首签人本人撤回')
            if action=='撤回补签' and pharmacist!=order['countersigner']:
                raise DomainError('WITHDRAW','只能由补签人本人撤回')
            late=order['late']
            if action.startswith('补签'):
                deadline=datetime.fromisoformat(order['first_at'])+timedelta(hours=COUNTERSIGN_GRACE_HOURS)
                late=int(datetime.fromisoformat(at)>deadline)
            new_state=TRANSITIONS[key]
            first_signer,first_at=order['first_signer'],order['first_at']
            countersigner,countersign_at=order['countersigner'],order['countersign_at']
            if action.startswith('首签'): first_signer,first_at=pharmacist,at
            if action.startswith('补签'): countersigner,countersign_at=pharmacist,at
            if action=='撤回首签': first_signer,first_at=None,None
            if action=='撤回补签': countersigner,countersign_at,late=None,None,0
            changed=apply_transition(conn,order,new_state,first_signer,first_at,countersigner,countersign_at,late,version)
            if not changed: raise DomainError('VERSION','放行结论已变化，请重新载入',409)
            append_ledger(conn,run_id,order_id,action_id,action,pharmacist,at,late if action.startswith('补签') else 0,new_state)
            return {'order':row_to_order(get_order(conn,order_id)),'replayed':False}
    except sqlite3.IntegrityError:
        with db() as conn:
            replay=find_replay(conn,action_id)
            if replay: return {'order':row_to_order(get_order(conn,replay['order_id'])),'replayed':True}
        raise
