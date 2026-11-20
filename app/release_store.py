import sqlite3
from app.store import connection
SCHEMA_ORDERS='''CREATE TABLE IF NOT EXISTS release_orders(
 order_id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL,
 demand TEXT NOT NULL,
 store TEXT, sku TEXT, lot TEXT, qty TEXT, expiry TEXT,
 state TEXT NOT NULL DEFAULT '待首签',
 first_signer TEXT, first_at TEXT,
 countersigner TEXT, countersign_at TEXT,
 late INTEGER NOT NULL DEFAULT 0,
 version INTEGER NOT NULL DEFAULT 1)'''
SCHEMA_LEDGER='''CREATE TABLE IF NOT EXISTS release_ledger(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,
 run_id TEXT NOT NULL,
 order_id TEXT NOT NULL,
 action_id TEXT NOT NULL UNIQUE,
 action TEXT NOT NULL,
 pharmacist TEXT NOT NULL,
 at TEXT NOT NULL,
 late INTEGER NOT NULL DEFAULT 0,
 state_after TEXT NOT NULL)'''
def db():
    conn=connection()
    conn.execute(SCHEMA_ORDERS)
    conn.execute(SCHEMA_LEDGER)
    return conn
def row_to_order(r):
    return {'order_id':r['order_id'],'run_id':r['run_id'],'需求单':r['demand'],'门店':r['store'],'药品':r['sku'],'批号':r['lot'],'调拨数量':r['qty'],'到期日':r['expiry'],'state':r['state'],'first_signer':r['first_signer'],'first_at':r['first_at'],'countersigner':r['countersigner'],'countersign_at':r['countersign_at'],'late':bool(r['late']),'version':r['version']}
def get_order(conn,order_id):
    return conn.execute('SELECT * FROM release_orders WHERE order_id=?',(order_id,)).fetchone()
def list_orders(run_id):
    with db() as conn:
        rows=conn.execute('SELECT * FROM release_orders WHERE run_id=? ORDER BY rowid',(run_id,)).fetchall()
    return [row_to_order(r) for r in rows]
def list_ledger(run_id):
    with db() as conn:
        rows=conn.execute('SELECT l.seq,l.order_id,l.action_id,l.action,l.pharmacist,l.at,l.late,l.state_after,o.demand,o.lot,o.store FROM release_ledger l JOIN release_orders o ON o.order_id=l.order_id WHERE l.run_id=? ORDER BY l.seq',(run_id,)).fetchall()
    return [{'seq':r['seq'],'order_id':r['order_id'],'action_id':r['action_id'],'需求单':r['demand'],'批号':r['lot'],'门店':r['store'],'action':r['action'],'pharmacist':r['pharmacist'],'at':r['at'],'late':bool(r['late']),'state_after':r['state_after']} for r in rows]
def ensure_orders(run):
    run_id=run['manifest']['run_id']
    with db() as conn:
        for index,r in enumerate(run['stages']['5']['rows']):
            conn.execute('INSERT OR IGNORE INTO release_orders(order_id,run_id,demand,store,sku,lot,qty,expiry) VALUES (?,?,?,?,?,?,?,?)',(f"{run_id}:{index}:{r['需求单']}:{r['批号']}",run_id,r['需求单'],r['门店'],r['药品'],r['批号'],str(r['调拨数量']),r['到期日']))
def find_replay(conn,action_id):
    return conn.execute('SELECT order_id FROM release_ledger WHERE action_id=?',(action_id,)).fetchone()
def apply_transition(conn,order,new_state,first_signer,first_at,countersigner,countersign_at,late,version):
    return conn.execute('UPDATE release_orders SET state=?,first_signer=?,first_at=?,countersigner=?,countersign_at=?,late=?,version=version+1 WHERE order_id=? AND version=?',(new_state,first_signer,first_at,countersigner,countersign_at,late,order['order_id'],version)).rowcount
def append_ledger(conn,run_id,order_id,action_id,action,pharmacist,at,late,state_after):
    conn.execute('INSERT INTO release_ledger(run_id,order_id,action_id,action,pharmacist,at,late,state_after) VALUES (?,?,?,?,?,?,?,?)',(run_id,order_id,action_id,action,pharmacist,at,late,state_after))
