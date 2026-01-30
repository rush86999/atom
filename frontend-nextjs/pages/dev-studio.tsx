import React, { useState, useEffect } from "react";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
    Cpu,
    Folder,
    Terminal,
    Code,
    Settings,
    Play,
    StopCircle,
    RefreshCw,
    File,
    AlertTriangle,
    Monitor,
} from "lucide-react";
import AgentConsole from "@/components/DevStudio/AgentConsole";
import SkillRunner from "@/components/DevStudio/SkillRunner";

// Tauri imports for desktop functionality
const { invoke } =
    typeof window !== "undefined" ? require("@tauri-apps/api") : { invoke: null };

const DevStudio = () => {
    const { toast } = useToast();
    const [systemInfo, setSystemInfo] = useState<any>(null);
    const [fileContent, setFileContent] = useState<string>("");
    const [selectedFile, setSelectedFile] = useState<string>("");
    const [directoryContents, setDirectoryContents] = useState<any[]>([]);
    const [currentDirectory, setCurrentDirectory] = useState<string>("");
    const [commandOutput, setCommandOutput] = useState<string>("");
    const [isExecuting, setIsExecuting] = useState<boolean>(false);
    const [command, setCommand] = useState<string>("");
    const [commandArgs, setCommandArgs] = useState<string>("");
    const [workingDir, setWorkingDir] = useState<string>("");

    // Load system information
    const loadSystemInfo = async () => {
        if (!invoke) {
            toast({
                title: "Desktop Only",
                description: "This feature is only available in the desktop app",
                variant: "error",
            });
            return;
        }

        try {
            const info = await invoke("get_system_info");
            setSystemInfo(info);
        } catch (error) {
            console.error("Failed to load system info:", error);
            toast({
                title: "Error",
                description: "Failed to load system information",
                variant: "error",
            });
        }
    };

    // Open file dialog
    const openFile = async () => {
        if (!invoke) return;

        try {
            const result = await invoke("open_file_dialog", {
                filters: [
                    [
                        "Code Files",
                        [
                            "js",
                            "ts",
                            "jsx",
                            "tsx",
                            "py",
                            "rs",
                            "go",
                            "java",
                            "cpp",
                            "c",
                            "html",
                            "css",
                            "scss",
                            "json",
                            "yaml",
                            "yml",
                        ],
                    ],
                    ["All Files", ["*"]],
                ],
            });

            if (result.success) {
                setSelectedFile(result.path);
                const content = await invoke("read_file_content", {
                    path: result.path,
                });
                if (content.success) {
                    setFileContent(content.content);
                }
            }
        } catch (error) {
            console.error("Failed to open file:", error);
        }
    };

    // Open folder dialog
    const openFolder = async () => {
        if (!invoke) return;

        try {
            const result = await invoke("open_folder_dialog");
            if (result.success) {
                setCurrentDirectory(result.path);
                const contents = await invoke("list_directory", { path: result.path });
                if (contents.success) {
                    setDirectoryContents(contents.entries);
                }
            }
        } catch (error) {
            console.error("Failed to open folder:", error);
        }
    };

    // Execute command
    const executeCommand = async () => {
        if (!invoke || !command.trim()) return;

        setIsExecuting(true);
        setCommandOutput("");

        try {
            const args = commandArgs.split(" ").filter((arg) => arg.trim());
            const result = await invoke("execute_command", {
                command: command.trim(),
                args: args,
                workingDir: workingDir || currentDirectory || undefined,
            });

            let output = "";
            if (result.success) {
                output += `Command executed successfully (exit code: ${result.exit_code})\n\n`;
            } else {
                output += `Command failed (exit code: ${result.exit_code})\n\n`;
            }

            if (result.stdout) {
                output += `STDOUT:\n${result.stdout}\n`;
            }

            if (result.stderr) {
                output += `STDERR:\n${result.stderr}\n`;
            }

            setCommandOutput(output);
        } catch (error) {
            setCommandOutput(`Error executing command: ${error}`);
        } finally {
            setIsExecuting(false);
        }
    };

    // Save file content
    const saveFile = async () => {
        if (!invoke || !selectedFile) return;

        try {
            const result = await invoke("write_file_content", {
                path: selectedFile,
                content: fileContent,
            });

            if (result.success) {
                toast({
                    title: "File Saved",
                    description: `Successfully saved ${selectedFile}`,
                    variant: "success",
                });
            }
        } catch (error) {
            toast({
                title: "Save Failed",
                description: `Failed to save file: ${error}`,
                variant: "error",
            });
        }
    };

    // Load directory contents
    const loadDirectory = async (path: string) => {
        if (!invoke) return;

        try {
            const contents = await invoke("list_directory", { path });
            if (contents.success) {
                setDirectoryContents(contents.entries);
                setCurrentDirectory(path);
            }
        } catch (error) {
            console.error("Failed to load directory:", error);
        }
    };

    useEffect(() => {
        loadSystemInfo();
    }, []);

    const commonCommands = [
        { name: "npm install", description: "Install dependencies" },
        { name: "npm run dev", description: "Start development server" },
        { name: "npm run build", description: "Build for production" },
        { name: "git status", description: "Check git status" },
        { name: "git pull", description: "Pull latest changes" },
        { name: "ls -la", description: "List directory contents" },
        { name: "pwd", description: "Print working directory" },
    ];

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-8">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Header */}
                <div className="space-y-2">
                    <h1 className="text-3xl font-bold tracking-tight">Dev Studio</h1>
                    <p className="text-muted-foreground">
                        Advanced development utilities and system integration for the ATOM desktop app
                    </p>
                </div>

                {!invoke && (
                    <Alert className="bg-yellow-50 border-yellow-200 text-yellow-800">
                        <AlertTriangle className="h-4 w-4" />
                        <AlertTitle>Desktop App Required</AlertTitle>
                        <AlertDescription>
                            These development tools are only available in the ATOM desktop
                            application. Please download and install the desktop app to
                            access these features.
                        </AlertDescription>
                    </Alert>
                )}

                <Tabs defaultValue="system" className="w-full">
                    <TabsList className="grid w-full grid-cols-4 mb-8">
                        <TabsTrigger value="system" className="flex items-center gap-2">
                            <Cpu className="h-4 w-4" />
                            System Info
                        </TabsTrigger>
                        <TabsTrigger value="explorer" className="flex items-center gap-2">
                            <Folder className="h-4 w-4" />
                            File Explorer
                        </TabsTrigger>
                        <TabsTrigger value="terminal" className="flex items-center gap-2">
                            <Terminal className="h-4 w-4" />
                            Skill Runner
                        </TabsTrigger>
                        <TabsTrigger value="editor" className="flex items-center gap-2">
                            <Code className="h-4 w-4" />
                            Code Editor
                        </TabsTrigger>
                        <TabsTrigger value="agent" className="flex items-center gap-2">
                            <Monitor className="h-4 w-4" />
                            Agent
                        </TabsTrigger>
                    </TabsList>

                    {/* System Info Panel */}
                    <TabsContent value="system" className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <Card>
                                <CardHeader>
                                    <CardTitle>Platform Information</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {systemInfo ? (
                                        <div className="space-y-4">
                                            <div className="flex justify-between items-center">
                                                <span className="font-medium">Platform:</span>
                                                <Badge variant="secondary">{systemInfo.platform}</Badge>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="font-medium">Architecture:</span>
                                                <Badge variant="outline">{systemInfo.architecture}</Badge>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="font-medium">Version:</span>
                                                <span>{systemInfo.version}</span>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="font-medium">Tauri Version:</span>
                                                <span>{systemInfo.tauri_version}</span>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center py-8 text-muted-foreground">
                                            Loading system information...
                                        </div>
                                    )}
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle>Available Features</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    {systemInfo?.features ? (
                                        <div className="space-y-3">
                                            {Object.entries(systemInfo.features).map(
                                                ([feature, enabled]) => (
                                                    <div key={feature} className="flex justify-between items-center">
                                                        <span>
                                                            {feature
                                                                .split("_")
                                                                .map(
                                                                    (word) =>
                                                                        word.charAt(0).toUpperCase() +
                                                                        word.slice(1),
                                                                )
                                                                .join(" ")}
                                                        </span>
                                                        <Badge variant={enabled ? "default" : "destructive"}>
                                                            {enabled ? "Enabled" : "Disabled"}
                                                        </Badge>
                                                    </div>
                                                ),
                                            )}
                                        </div>
                                    ) : (
                                        <div className="flex items-center justify-center py-8 text-muted-foreground">
                                            Loading features...
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>

                        <Button onClick={loadSystemInfo} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            Refresh System Info
                        </Button>
                    </TabsContent>

                    {/* File Explorer Panel */}
                    <TabsContent value="explorer" className="space-y-6">
                        <div className="flex items-center gap-4">
                            <Button onClick={openFolder} className="gap-2">
                                <Folder className="h-4 w-4" />
                                Open Folder
                            </Button>
                            <Button variant="secondary" onClick={openFile} className="gap-2">
                                <File className="h-4 w-4" />
                                Open File
                            </Button>
                            <span className="text-sm text-muted-foreground">
                                {currentDirectory || "No folder selected"}
                            </span>
                        </div>

                        {directoryContents.length > 0 && (
                            <Card>
                                <CardHeader>
                                    <CardTitle>Directory Contents</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="rounded-md border">
                                        <table className="w-full text-sm text-left">
                                            <thead className="bg-muted/50 text-muted-foreground">
                                                <tr>
                                                    <th className="h-10 px-4 font-medium">Name</th>
                                                    <th className="h-10 px-4 font-medium">Type</th>
                                                    <th className="h-10 px-4 font-medium">Size</th>
                                                    <th className="h-10 px-4 font-medium">Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {directoryContents.map((item, index) => (
                                                    <tr key={index} className="border-t hover:bg-muted/50">
                                                        <td className="p-4">
                                                            <div className="flex items-center gap-2">
                                                                {item.is_directory ? (
                                                                    <Folder className="h-4 w-4 text-blue-500" />
                                                                ) : (
                                                                    <File className="h-4 w-4 text-gray-500" />
                                                                )}
                                                                <span>{item.name}</span>
                                                            </div>
                                                        </td>
                                                        <td className="p-4">
                                                            <Badge variant={item.is_directory ? "default" : "secondary"}>
                                                                {item.is_directory ? "Directory" : "File"}
                                                            </Badge>
                                                        </td>
                                                        <td className="p-4">
                                                            {item.is_directory
                                                                ? "-"
                                                                : `${(item.size / 1024).toFixed(1)} KB`}
                                                        </td>
                                                        <td className="p-4">
                                                            {item.is_directory ? (
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={() => loadDirectory(item.path)}
                                                                >
                                                                    Open
                                                                </Button>
                                                            ) : (
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={async () => {
                                                                        setSelectedFile(item.path);
                                                                        const content = await invoke(
                                                                            "read_file_content",
                                                                            { path: item.path },
                                                                        );
                                                                        if (content.success) {
                                                                            setFileContent(content.content);
                                                                        }
                                                                    }}
                                                                >
                                                                    View
                                                                </Button>
                                                            )}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>

                    {/* Skill Runner Panel */}
                    <TabsContent value="terminal" className="space-y-6">
                        <SkillRunner />
                    </TabsContent>

                    {/* Code Editor Panel */}
                    <TabsContent value="editor" className="space-y-6">
                        <div className="flex items-center justify-between">
                            <span className="font-medium">
                                {selectedFile
                                    ? `Editing: ${selectedFile}`
                                    : "No file selected"}
                            </span>
                            <div className="flex items-center gap-2">
                                <Button variant="outline" onClick={openFile} className="gap-2">
                                    <File className="h-4 w-4" />
                                    Open File
                                </Button>
                                {selectedFile && (
                                    <Button onClick={saveFile} className="gap-2">
                                        <Settings className="h-4 w-4" />
                                        Save File
                                    </Button>
                                )}
                            </div>
                        </div>

                        {selectedFile ? (
                            <Textarea
                                value={fileContent}
                                onChange={(e) => setFileContent(e.target.value)}
                                className="min-h-[500px] font-mono text-sm"
                                placeholder="File content will appear here..."
                            />
                        ) : (
                            <Card>
                                <CardContent className="flex flex-col items-center justify-center py-16 text-center">
                                    <File className="h-12 w-12 text-muted-foreground mb-4" />
                                    <p className="text-lg font-medium mb-2">No file selected</p>
                                    <p className="text-muted-foreground mb-6">
                                        Open a file to start editing code directly in Dev Studio.
                                    </p>
                                    <Button onClick={openFile} className="gap-2">
                                        <File className="h-4 w-4" />
                                        Open File
                                    </Button>
                                </CardContent>
                            </Card>
                        )}
                    </TabsContent>


                    {/* Agent Console Panel */}
                    <TabsContent value="agent" className="space-y-6">
                        <AgentConsole />
                    </TabsContent>
                </Tabs>
            </div>
        </div>

    );
};

export default DevStudio;
