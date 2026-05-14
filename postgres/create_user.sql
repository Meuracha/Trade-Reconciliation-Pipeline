-- Create user if not exists
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = current_setting('app.db_user')) THEN
    EXECUTE format('CREATE USER %I WITH PASSWORD %L',
      current_setting('app.db_user'),
      current_setting('app.db_password')
    );
  END IF;
END
$$;
