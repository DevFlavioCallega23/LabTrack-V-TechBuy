import sqlite3, os

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'labtrack.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Delete old machine 02 components
cur.execute("DELETE FROM component WHERE protocol_id=49 AND unit='02'")

# Find max id
max_id = cur.execute("SELECT MAX(id) FROM component").fetchone()[0] or 0

# Add the 5 PE components for machine 02
comps = [
    (max_id+1, 49, 'processador', 'I5-2400', None, '02', 'Máquina 02', 200, 1, None),
    (max_id+2, 49, 'placa_mae', '1155 PC-Tech', None, '02', 'Máquina 02', 201, 1, None),
    (max_id+3, 49, 'ram', '8GB DDR3 PC-Tech', None, '02', 'Máquina 02', 202, 1, None),
    (max_id+4, 49, 'ssd', '120GB WD Green', None, '02', 'Máquina 02', 203, 1, None),
    (max_id+5, 49, 'fonte', '230W C3Tech', '143893', '02', 'Máquina 02', 204, 1, None),
]

for c in comps:
    cur.execute(
        "INSERT INTO component (id, protocol_id, component_type, specification, serial_number, unit, machine_name, sort_order, is_prebuilt, machine_ref_ns) VALUES (?,?,?,?,?,?,?,?,?,?)",
        c
    )

conn.commit()

cur.execute("SELECT id, unit, component_type, specification, serial_number, is_prebuilt, sort_order FROM component WHERE protocol_id = 49 ORDER BY sort_order")
for r in cur.fetchall():
    print(f'  id={r[0]} Mq {r[1]}: {r[2]} | {r[3]} | ns={r[4]} | pe={r[5]}')

conn.close()
print(f'\nTotal components: {len(comps) + 5}')
print('Done')
