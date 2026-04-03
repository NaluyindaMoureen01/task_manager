import os
import sys
import psycopg2

def run_migrations():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('ERROR: DATABASE_URL environment variable is not set.')
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    cur.execute('CREATE TABLE IF NOT EXISTS tasks (id SERIAL PRIMARY KEY, title TEXT NOT NULL, completed BOOLEAN NOT NULL DEFAULT FALSE, due_date DATE, priority TEXT NOT NULL DEFAULT \'medium\');')

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

    conn.commit()
    cur.close()
    conn.close()
    print('Migration complete.')

if __name__ == '__main__':
    run_migrations()
