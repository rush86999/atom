CREATE TABLE IF NOT EXISTS public.workflows (
    id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(),
    user_id uuid NOT NULL,
    name TEXT NOT NULL,
    definition JSONB NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    celery_task_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_user_id FOREIGN KEY(user_id) REFERENCES public."User"(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflows_user_id ON public.workflows(user_id);

CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER set_updated_at_workflows BEFORE UPDATE ON public.workflows FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
