CREATE TABLE public.email_reminders (
    id uuid DEFAULT public.gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    email_id character varying NOT NULL,
    service character varying NOT NULL,
    remind_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON UPDATE restrict ON DELETE cascade
);
