CREATE TABLE IF NOT EXISTS public.workflow_components (
    id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    service TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(service, name)
);

CREATE INDEX IF NOT EXISTS idx_workflow_components_type ON public.workflow_components(type);

CREATE TRIGGER set_updated_at_workflow_components BEFORE UPDATE ON public.workflow_components FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
