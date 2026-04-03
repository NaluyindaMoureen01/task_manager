from flask import Flask, request, jsonify, render_template
import os

try:
    import psycopg2
    HAS_PG = True
except ImportError:
    import sqlite3
    HAS_PG = False

app = Flask(__name__)

def get_db_connection():
    if HAS_PG:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            raise RuntimeError('DATABASE_URL is not set for PostgreSQL connection')
        return psycopg2.connect(db_url)

    conn = sqlite3.connect('tasks.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    if HAS_PG:
        cur.execute('CREATE TABLE IF NOT EXISTS tasks (id SERIAL PRIMARY KEY, title TEXT NOT NULL, completed BOOLEAN NOT NULL DEFAULT FALSE, due_date DATE, priority TEXT NOT NULL DEFAULT \'medium\');')
        # Ensure old tables migrate
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'tasks' AND column_name = 'completed'
                ) THEN
                    ALTER TABLE tasks ADD COLUMN completed BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'tasks' AND column_name = 'due_date'
                ) THEN
                    ALTER TABLE tasks ADD COLUMN due_date DATE;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'tasks' AND column_name = 'priority'
                ) THEN
                    ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'medium';
                END IF;
            END;
            $$;
        """)
    else:
        cur.execute('CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0, due_date TEXT, priority TEXT NOT NULL DEFAULT "medium");')
        # SQLite has no boolean type; store as 0/1.
        cur.execute("""
            PRAGMA table_info(tasks);
        """)
        columns = [row[1] for row in cur.fetchall()]
        if 'completed' not in columns:
            cur.execute('ALTER TABLE tasks ADD COLUMN completed INTEGER NOT NULL DEFAULT 0;')
        if 'due_date' not in columns:
            cur.execute('ALTER TABLE tasks ADD COLUMN due_date TEXT;')
        if 'priority' not in columns:
            cur.execute('ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT "medium";')
    conn.commit()
    cur.close()
    conn.close()


@app.route('/')
def home():
    return render_template('index.html')


def _rows_to_list(rows):
    results = []
    for row in rows:
        if HAS_PG:
            results.append({
                'id': row[0],
                'title': row[1],
                'completed': row[2],
                'due_date': row[3],
                'priority': row[4]
            })
        else:
            results.append({
                'id': row['id'],
                'title': row['title'],
                'completed': bool(row['completed']),
                'due_date': row['due_date'],
                'priority': row['priority']
            })
    return results
    results = []
    for row in rows:
        if HAS_PG:
            results.append({
                'id': row[0],
                'title': row[1],
                'completed': row[2],
                'due_date': row[3],
                'priority': row[4]
            })
        else:
            results.append({
                'id': row['id'],
                'title': row['title'],
                'completed': bool(row['completed']),
                'due_date': row['due_date'],
                'priority': row['priority']
            })
    return results


@app.route('/tasks', methods=['GET'])
def get_tasks():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM tasks;')
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(_rows_to_list(rows))


@app.route('/tasks', methods=['POST'])
def add_task():
    data = request.json or {}
    title = data.get('title')
    if not title:
        return jsonify({'error': 'title is required'}), 400

    completed = bool(data.get('completed', False))
    due_date = data.get('due_date')
    priority = data.get('priority', 'medium').lower()
    if priority not in ['low', 'medium', 'high']:
        return jsonify({'error': 'priority must be low, medium, or high'}), 400

    conn = get_db_connection()
    cur = conn.cursor()
    if HAS_PG:
        cur.execute('INSERT INTO tasks (title, completed, due_date, priority) VALUES (%s, %s, %s, %s);', (title, completed, due_date, priority))
    else:
        cur.execute('INSERT INTO tasks (title, completed, due_date, priority) VALUES (?, ?, ?, ?);', (title, int(completed), due_date, priority))
    conn.commit()
    cur.close()
    conn.close()
    return {'message': 'Task added'}, 201


@app.route('/tasks/<int:id>', methods=['PUT'])
def update_task(id):
    data = request.json or {}
    title = data.get('title')
    completed = data.get('completed')
    due_date = data.get('due_date')
    priority = data.get('priority')

    if title is None and completed is None and due_date is None and priority is None:
        return jsonify({'error': 'nothing to update'}), 400

    set_clauses = []
    params = []

    if title is not None:
        set_clauses.append('title = %s' if HAS_PG else 'title = ?')
        params.append(title)

    if completed is not None:
        set_clauses.append('completed = %s' if HAS_PG else 'completed = ?')
        params.append(bool(completed) if HAS_PG else int(bool(completed)))

    if due_date is not None:
        set_clauses.append('due_date = %s' if HAS_PG else 'due_date = ?')
        params.append(due_date)

    if priority is not None:
        p = priority.lower()
        if p not in ['low', 'medium', 'high']:
            return jsonify({'error': 'priority must be low, medium, or high'}), 400
        set_clauses.append('priority = %s' if HAS_PG else 'priority = ?')
        params.append(p)

    params.append(id)

    conn = get_db_connection()
    cur = conn.cursor()
    query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = {'%s' if HAS_PG else '?'};"
    cur.execute(query, tuple(params))
    if cur.rowcount == 0:
        cur.close()
        conn.close()
        return jsonify({'error': 'task not found'}), 404

    conn.commit()
    cur.close()
    conn.close()

    return {'message': 'Task updated'}


@app.route('/tasks/<int:id>', methods=['DELETE'])
def delete_task(id):
    conn = get_db_connection()
    cur = conn.cursor()
    if HAS_PG:
        cur.execute('DELETE FROM tasks WHERE id=%s;', (id,))
    else:
        cur.execute('DELETE FROM tasks WHERE id=?;', (id,))
    conn.commit()
    cur.close()
    conn.close()

    return {'message': 'Deleted'}


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)