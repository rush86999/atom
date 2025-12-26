import React from 'react';
import Head from 'next/head';
import TemplateGallery from '@/components/Automations/TemplateGallery';
import { useRouter } from 'next/router';
import { useToast } from '@/components/ui/use-toast';

/**
 * Workflow Templates Page
 * 
 * Browse and use pre-built workflow automation templates
 * Activepieces-style template marketplace
 */
export default function TemplatesPage() {
    const router = useRouter();
    const { toast } = useToast();

    const handleUseTemplate = (template: any) => {
        // Navigate to workflow builder with template data
        toast({
            title: "Template Selected",
            description: `Setting up "${template.name}"...`,
        });

        // Store template in session and redirect to builder
        sessionStorage.setItem('selectedTemplate', JSON.stringify(template));
        router.push('/automations/builder?template=' + template.id);
    };

    return (
        <>
            <Head>
                <title>Workflow Templates | Atom</title>
                <meta name="description" content="Browse pre-built workflow automation templates. Get started in minutes with templates for Sales, Marketing, Support, and more." />
            </Head>
            <div className="h-screen">
                <TemplateGallery onUseTemplate={handleUseTemplate} />
            </div>
        </>
    );
}
