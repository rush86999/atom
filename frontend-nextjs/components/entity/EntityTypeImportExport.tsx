import React, { useState } from 'react';
import { 
  Download, 
  Upload, 
  FileJson, 
  FileText, 
  AlertCircle, 
  CheckCircle2, 
  Loader2,
  X,
  Plus,
  FileUp
} from 'lucide-react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogDescription,
  DialogFooter
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from 'sonner';
import { parseEntityTypeDefinition, importEntityTypes, ImportError } from '@/src/lib/importers/entityTypeImporter';
import yaml from 'js-yaml';
import { useSession } from 'next-auth/react';

interface EntityType {
  slug: string;
  display_name: string;
  description?: string;
  json_schema: any;
}

interface EntityTypeImportExportProps {
  isOpen: boolean;
  onClose: () => void;
  entityTypes: EntityType[];
  onImportComplete: () => void;
}

export const EntityTypeImportExport: React.FC<EntityTypeImportExportProps> = ({
  isOpen,
  onClose,
  entityTypes,
  onImportComplete
}) => {
  const { data: session } = useSession();
  const workspaceId = (session as any)?.user?.workspace_id || 'default';
  
  const [importMode, setImportMode] = useState<'upload' | 'paste'>('upload');
  const [pastedContent, setPastedContent] = useState('');
  const [importing, setImporting] = useState(false);
  const [results, setResults] = useState<{ success: number; errors: ImportError[] } | null>(null);

  const handleExport = (type: 'json' | 'yaml', singleType?: EntityType) => {
    const data = singleType || entityTypes;
    const content = type === 'json' 
      ? JSON.stringify(data, null, 2)
      : yaml.dump(data);
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `entity_types_${new Date().toISOString().split('T')[0]}.${type}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    toast.success(`${type.toUpperCase()} Exported successfully`);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setImporting(true);
    setResults(null);
    
    const definitions: any[] = [];
    const localErrors: ImportError[] = [];

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        try {
            const content = await file.text();
            const parsed = parseEntityTypeDefinition(content, file.name);
            if (Array.isArray(parsed)) {
                definitions.push(...parsed);
            } else {
                definitions.push(parsed);
            }
        } catch (err: any) {
            localErrors.push({ file: file.name, error: err.message });
        }
    }

    if (definitions.length > 0) {
        const importResult = await importEntityTypes(definitions, workspaceId);
        setResults({
            success: importResult.success,
            errors: [...localErrors, ...importResult.errors]
        });
        if (importResult.success > 0) {
            onImportComplete();
        }
    } else if (localErrors.length > 0) {
        setResults({ success: 0, errors: localErrors });
    }
    
    setImporting(false);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl bg-zinc-950 border-white/10 text-white shadow-2xl">
        <DialogHeader>
          <DialogTitle className="text-xl font-black uppercase tracking-widest flex items-center gap-2">
            <Upload className="w-5 h-5 text-primary" />
            Portability Engine
          </DialogTitle>
          <DialogDescription className="text-white/40 text-[11px] font-bold uppercase">
            Sync your entity ecosystem across systems and workspaces
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="export" className="mt-4">
          <TabsList className="bg-white/5 border border-white/10 w-full p-1 h-12">
            <TabsTrigger value="export" className="flex-1 text-[10px] font-black uppercase data-[state=active]:bg-primary/20 data-[state=active]:text-primary">
              <Download className="w-3 h-3 mr-2" /> Export definitions
            </TabsTrigger>
            <TabsTrigger value="import" className="flex-1 text-[10px] font-black uppercase data-[state=active]:bg-primary/20 data-[state=active]:text-primary">
              <Upload className="w-3 h-3 mr-2" /> Import definitions
            </TabsTrigger>
          </TabsList>

          <TabsContent value="export" className="py-6 space-y-6">
            <div className="bg-white/5 border border-white/5 rounded-xl p-6 flex flex-col items-center text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                <FileJson className="w-6 h-6 text-primary" />
              </div>
              <div>
                <h4 className="text-sm font-bold text-white">Export Full Registry</h4>
                <p className="text-[10px] text-white/40 uppercase tracking-tighter mt-1">Download all {entityTypes.length} custom entity types in your preferred format</p>
              </div>
              <div className="flex gap-3 w-full">
                <Button onClick={() => handleExport('json')} variant="outline" className="flex-1 border-white/10 hover:bg-white/5 text-[10px] font-black uppercase">
                  <FileJson className="w-4 h-4 mr-2" /> JSON format
                </Button>
                <Button onClick={() => handleExport('yaml')} variant="outline" className="flex-1 border-white/10 hover:bg-white/5 text-[10px] font-black uppercase">
                  <FileText className="w-4 h-4 mr-2" /> YAML format
                </Button>
              </div>
            </div>

            <div className="space-y-3">
              <span className="text-[10px] font-black text-white/30 uppercase tracking-widest px-1">Specific types</span>
              <div className="max-h-48 overflow-y-auto space-y-2 custom-scrollbar pr-2">
                {entityTypes.map(et => (
                  <div key={et.slug} className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5 group hover:border-primary/30 transition-all">
                    <div className="flex flex-col">
                      <span className="text-xs font-bold text-white/90">{et.display_name}</span>
                      <code className="text-[8px] text-primary/60 font-mono italic">{et.slug}</code>
                    </div>
                    <div className="flex gap-1">
                      <Button onClick={() => handleExport('yaml', et)} variant="ghost" size="sm" className="h-7 px-2 text-[9px] font-black uppercase opacity-0 group-hover:opacity-100 hover:text-primary transition-all">
                        YAML
                      </Button>
                      <Button onClick={() => handleExport('json', et)} variant="ghost" size="sm" className="h-7 px-2 text-[9px] font-black uppercase opacity-0 group-hover:opacity-100 hover:text-primary transition-all">
                        JSON
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="import" className="py-6 space-y-6">
            {!results ? (
              <div className="space-y-4">
                <div className="relative group cursor-pointer">
                  <input 
                    type="file" 
                    multiple 
                    accept=".json,.yaml,.yml"
                    onChange={handleFileUpload}
                    className="absolute inset-0 w-full h-full opacity-0 z-10 cursor-pointer" 
                  />
                  <div className="border-2 border-dashed border-white/10 group-hover:border-primary/50 rounded-2xl p-10 flex flex-col items-center justify-center bg-white/[0.02] group-hover:bg-primary/5 transition-all">
                    <div className="p-4 bg-white/5 rounded-full mb-4 group-hover:scale-110 transition-transform">
                      {importing ? (
                        <Loader2 className="w-8 h-8 text-primary animate-spin" />
                      ) : (
                        <FileUp className="w-8 h-8 text-primary" />
                      )}
                    </div>
                    <h4 className="text-sm font-bold text-white mb-1">
                      {importing ? 'Processing files...' : 'Drop definitions here'}
                    </h4>
                    <p className="text-[10px] text-white/40 uppercase font-black tracking-tighter">
                      Support for JSON and YAML schema bundles
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-6 bg-white/5 border border-white/5 rounded-2xl p-6 animate-in zoom-in-95 duration-300">
                <div className="flex items-center justify-between px-2">
                  <h4 className="text-sm font-black text-white uppercase tracking-widest">Import Finished</h4>
                  <Button variant="ghost" size="sm" onClick={() => setResults(null)} className="h-8 text-[10px] font-black uppercase">
                    Clear Results
                  </Button>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-xl flex items-center gap-3">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <div className="flex flex-col">
                      <span className="text-2xl font-black text-emerald-400 leading-none">{results.success}</span>
                      <span className="text-[9px] font-bold text-emerald-500/50 uppercase">Successes</span>
                    </div>
                  </div>
                  <div className="bg-rose-500/10 border border-rose-500/20 p-4 rounded-xl flex items-center gap-3">
                    <AlertCircle className="w-5 h-5 text-rose-400" />
                    <div className="flex flex-col">
                      <span className="text-2xl font-black text-rose-400 leading-none">{results.errors.length}</span>
                      <span className="text-[9px] font-bold text-rose-500/50 uppercase">Failures</span>
                    </div>
                  </div>
                </div>

                {results.errors.length > 0 && (
                  <div className="space-y-3">
                    <span className="text-[10px] font-black text-rose-500/50 uppercase tracking-widest px-1">Error breakdown</span>
                    <div className="max-h-36 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
                      {results.errors.map((err, i) => (
                        <div key={i} className="bg-rose-500/5 border border-rose-500/10 p-2.5 rounded flex flex-col">
                          <span className="text-[10px] font-bold text-rose-300">{err.file}</span>
                          <span className="text-[9px] text-rose-400/60 leading-tight italic mt-1">{err.error}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter className="border-t border-white/10 pt-4 mt-2">
          <Button onClick={onClose} variant="ghost" className="text-[10px] font-black uppercase tracking-widest text-white/40 hover:text-white">
            Close Engine
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
