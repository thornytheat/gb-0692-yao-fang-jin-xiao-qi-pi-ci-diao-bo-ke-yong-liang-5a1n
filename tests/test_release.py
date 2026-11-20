import pytest
def make_run(client):
    return client.post('/api/run',json={}).get_json()['manifest']['run_id']
def orders(client,run_id):
    return client.get(f'/api/release/orders?run_id={run_id}').get_json()['orders']
def ledger(client,run_id):
    return client.get(f'/api/release/ledger?run_id={run_id}').get_json()['ledger']
def sign(client,run_id,order,action,pharmacist,action_id,at=None):
    body={'run_id':run_id,'order_id':order['order_id'],'action':action,'pharmacist':pharmacist,'action_id':action_id,'version':order['version']}
    if at: body['at']=at
    return client.post('/api/release/sign',json=body)
@pytest.fixture
def setup(client):
    run_id=make_run(client)
    return client,run_id,orders(client,run_id)
def test_orders_initialized_pending_first(setup):
    client,run_id,found=setup
    assert len(found)>0
    assert all(o['state']=='待首签' for o in found)
    assert orders(client,run_id)==found
def test_first_sign_is_conditional_release(setup):
    client,run_id,found=setup
    r=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()
    assert r['order']['state']=='待补签' and r['order']['first_signer']=='张三'
    assert r['replayed'] is False
def test_countersign_by_other_releases(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()['order']
    r=sign(client,run_id,o,'补签通过','李四','a2').get_json()
    assert r['order']['state']=='已放行' and r['order']['countersigner']=='李四'
def test_same_pharmacist_cannot_sign_twice(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()['order']
    r=sign(client,run_id,o,'补签通过','张三','a2')
    assert r.status_code==422 and r.get_json()['code']=='DUAL'
    after=[x for x in orders(client,run_id) if x['order_id']==o['order_id']][0]
    assert after['state']=='待补签'
    assert [e['action'] for e in ledger(client,run_id)]==['首签通过']
def test_first_reject_blocks(setup):
    client,run_id,found=setup
    r=sign(client,run_id,found[0],'首签驳回','张三','a1').get_json()
    assert r['order']['state']=='被拦下'
def test_countersign_reject_blocks(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()['order']
    r=sign(client,run_id,o,'补签驳回','李四','a2').get_json()
    assert r['order']['state']=='被拦下'
def test_retry_same_action_id_adds_no_signature(setup):
    client,run_id,found=setup
    first=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()
    second=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()
    assert second['replayed'] is True and second['order']['state']==first['order']['state']
    assert len(ledger(client,run_id))==1
def test_stale_version_keeps_old_conclusion(setup):
    client,run_id,found=setup
    sign(client,run_id,found[0],'首签通过','张三','a1')
    stale={**found[0],'version':found[0]['version']}
    r=sign(client,run_id,stale,'补签通过','李四','a2')
    assert r.status_code==409
    after=[x for x in orders(client,run_id) if x['order_id']==found[0]['order_id']][0]
    assert after['state']=='待补签' and after['countersigner'] is None
    assert len(ledger(client,run_id))==1
def test_withdraw_countersign_reopens_and_keeps_archive(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()['order']
    o=sign(client,run_id,o,'补签通过','李四','a2').get_json()['order']
    assert o['state']=='已放行'
    r=sign(client,run_id,o,'撤回补签','李四','a3').get_json()
    assert r['order']['state']=='待补签' and r['order']['countersigner'] is None
    entries=ledger(client,run_id)
    assert [e['action'] for e in entries]==['首签通过','补签通过','撤回补签']
    assert len({e['action_id'] for e in entries})==3
def test_withdraw_first_sign_blocks(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()['order']
    r=sign(client,run_id,o,'撤回首签','张三','a2').get_json()
    assert r['order']['state']=='被拦下'
def test_withdraw_requires_self(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1').get_json()['order']
    o=sign(client,run_id,o,'补签通过','李四','a2').get_json()['order']
    r=sign(client,run_id,o,'撤回补签','张三','a3')
    assert r.status_code==422 and r.get_json()['code']=='WITHDRAW'
    after=[x for x in orders(client,run_id) if x['order_id']==o['order_id']][0]
    assert after['state']=='已放行'
def test_late_countersign_flagged(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1',at='2026-11-19T20:00:00+00:00').get_json()['order']
    r=sign(client,run_id,o,'补签通过','李四','a2',at='2026-11-20T09:00:00+00:00').get_json()['order']
    assert r['state']=='已放行' and r['late'] is True
    assert ledger(client,run_id)[1]['late'] is True
def test_ontime_countersign_not_late(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签通过','张三','a1',at='2026-11-19T20:00:00+00:00').get_json()['order']
    r=sign(client,run_id,o,'补签通过','李四','a2',at='2026-11-20T07:59:59+00:00').get_json()['order']
    assert r['late'] is False
def test_ledger_is_append_only(setup):
    client,run_id,found=setup
    o=found[0]
    for action,pharmacist,key in [('首签通过','张三','a1'),('补签通过','李四','a2'),('撤回补签','李四','a3'),('补签通过','王五','a4')]:
        o=sign(client,run_id,o,action,pharmacist,key).get_json()['order']
    entries=ledger(client,run_id)
    assert [e['action'] for e in entries]==['首签通过','补签通过','撤回补签','补签通过']
    assert [e['seq'] for e in entries]==sorted(e['seq'] for e in entries)
    assert o['state']=='已放行' and o['countersigner']=='王五'
def test_blocked_is_terminal(setup):
    client,run_id,found=setup
    o=sign(client,run_id,found[0],'首签驳回','张三','a1').get_json()['order']
    r=sign(client,run_id,o,'首签通过','李四','a2')
    assert r.status_code==409 and r.get_json()['code']=='STATE'
def test_sign_validation(setup):
    client,run_id,found=setup
    assert sign(client,run_id,found[0],'首签通过','','a1').status_code==422
    assert sign(client,run_id,found[0],'首签通过','张三','').status_code==422
    assert sign(client,run_id,found[0],'放行','张三','a1').status_code==422
    missing={**found[0],'order_id':'no-such-order'}
    assert sign(client,run_id,missing,'首签通过','张三','a1').status_code==404
def test_release_page(client):
    run_id=make_run(client)
    page=client.get(f'/release?run_id={run_id}')
    assert page.status_code==200 and '夜班放行'.encode() in page.data
