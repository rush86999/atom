CREATE TABLE IF NOT EXISTS public.workflow_component_schemas (
    id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(),
    component_id uuid NOT NULL,
    type TEXT NOT NULL,
    schema JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(component_id, type),
    CONSTRAINT fk_component_id FOREIGN KEY(component_id) REFERENCES public.workflow_components(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_component_schemas_component_id ON public.workflow_component_schemas(component_id);

CREATE TRIGGER set_updated_at_workflow_component_schemas BEFORE UPDATE ON public.workflow_component_schemas FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();
