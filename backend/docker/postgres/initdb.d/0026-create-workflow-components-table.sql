-- Create workflow_components table for dynamic workflow system
CREATE TABLE IF NOT EXISTS public.workflow_components (
    id uuid PRIMARY KEY DEFAULT public.gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('trigger', 'action')),
    service TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'general',
    icon TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(service, name)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_workflow_components_type ON public.workflow_components(type);
CREATE INDEX IF NOT EXISTS idx_workflow_components_service ON public.workflow_components(service);
CREATE INDEX IF NOT EXISTS idx_workflow_components_category ON public.workflow_components(category);
CREATE INDEX IF NOT EXISTS idx_workflow_components_active ON public.workflow_components(is_active);

-- Create updated_at trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updated_at
DROP TRIGGER IF EXISTS set_updated_at_workflow_components ON public.workflow_components;
CREATE TRIGGER set_updated_at_workflow_components
BEFORE UPDATE ON public.workflow_components
FOR EACH ROW
EXECUTE FUNCTION public.set_current_timestamp_updated_at();
