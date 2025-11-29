import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Code,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Progress,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Textarea,
  FormControl,
  FormLabel,
  Switch,
  IconButton,
  Tooltip,
} from "@chakra-ui/react";
import {
  FiFolder,
  FiFile,
  FiTerminal,
  FiCpu,
  FiSettings,
  FiPlay,
  FiStopCircle,
  FiRefreshCw,
  FiInfo,
  FiCode,
  FiDatabase,
  FiServer,
  FiGitBranch,
  FiPackage,
  FiShield,
  FiMonitor,
} from "react-icons/fi";

// Tauri imports for desktop functionality
const { invoke } =
  typeof window !== "undefined" ? require("@tauri-apps/api") : { invoke: null };

const DevTools = () => {
  const toast = useToast();
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

  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");
  const accentColor = useColorModeValue("blue.500", "blue.300");

  // Load system information
  const loadSystemInfo = async () => {
    if (!invoke) {
      toast({
        title: "Desktop Only",
        description: "This feature is only available in the desktop app",
        status: "warning",
        duration: 3000,
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
        status: "error",
        duration: 3000,
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
          status: "success",
          duration: 2000,
        });
      }
    } catch (error) {
      toast({
        title: "Save Failed",
        description: `Failed to save file: ${error}`,
        status: "error",
        duration: 3000,
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
  }, [loadSystemInfo]);

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
    <Box p={6} maxW="1200px" mx="auto">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="xl" mb={2}>
            Development Tools
          </Heading>
          <Text color="gray.600">
            Advanced development utilities and system integration for the ATOM
            desktop app
          </Text>
        </Box>

        {!invoke && (
          <Alert status="warning" borderRadius="md">
            <AlertIcon />
            <Box>
              <AlertTitle>Desktop App Required</AlertTitle>
              <AlertDescription>
                These development tools are only available in the ATOM desktop
                application. Please download and install the desktop app to
                access these features.
              </AlertDescription>
            </Box>
          </Alert>
        )}

        <Tabs colorScheme="blue">
          <TabList>
            <Tab>
              <Icon as={FiCpu} mr={2} />
              System Info
            </Tab>
            <Tab>
              <Icon as={FiFolder} mr={2} />
              File Explorer
            </Tab>
            <Tab>
              <Icon as={FiTerminal} mr={2} />
              Command Runner
            </Tab>
            <Tab>
              <Icon as={FiCode} mr={2} />
              Code Editor
            </Tab>
          </TabList>

          <TabPanels>
            {/* System Info Panel */}
            <TabPanel>
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                <Card>
                  <CardHeader>
                    <Heading size="md">Platform Information</Heading>
                  </CardHeader>
                  <CardBody>
                    {systemInfo ? (
                      <VStack align="stretch" spacing={3}>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Platform:</Text>
                          <Badge colorScheme="blue">
                            {systemInfo.platform}
                          </Badge>
                        </HStack>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Architecture:</Text>
                          <Badge colorScheme="green">
                            {systemInfo.architecture}
                          </Badge>
                        </HStack>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Version:</Text>
                          <Text>{systemInfo.version}</Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text fontWeight="medium">Tauri Version:</Text>
                          <Text>{systemInfo.tauri_version}</Text>
                        </HStack>
                      </VStack>
                    ) : (
                      <Text>Loading system information...</Text>
                    )}
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="md">Available Features</Heading>
                  </CardHeader>
                  <CardBody>
                    {systemInfo?.features ? (
                      <VStack align="stretch" spacing={2}>
                        {Object.entries(systemInfo.features).map(
                          ([feature, enabled]) => (
                            <HStack key={feature} justify="space-between">
                              <Text>
                                {feature
                                  .split("_")
                                  .map(
                                    (word) =>
                                      word.charAt(0).toUpperCase() +
                                      word.slice(1),
                                  )
                                  .join(" ")}
                                :
                              </Text>
                              <Badge colorScheme={enabled ? "green" : "red"}>
                                {enabled ? "Enabled" : "Disabled"}
                              </Badge>
                            </HStack>
                          ),
                        )}
                      </VStack>
                    ) : (
                      <Text>Loading features...</Text>
                    )}
                  </CardBody>
                </Card>
              </SimpleGrid>

              <Button
                mt={4}
                leftIcon={<FiRefreshCw />}
                onClick={loadSystemInfo}
                colorScheme="blue"
              >
                Refresh System Info
              </Button>
            </TabPanel>

            {/* File Explorer Panel */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack>
                  <Button
                    leftIcon={<FiFolder />}
                    onClick={openFolder}
                    colorScheme="blue"
                  >
                    Open Folder
                  </Button>
                  <Button
                    leftIcon={<FiFile />}
                    onClick={openFile}
                    colorScheme="green"
                  >
                    Open File
                  </Button>
                  <Text color="gray.600" fontSize="sm">
                    {currentDirectory || "No folder selected"}
                  </Text>
                </HStack>

                {directoryContents.length > 0 && (
                  <Card>
                    <CardHeader>
                      <Heading size="md">Directory Contents</Heading>
                    </CardHeader>
                    <CardBody>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Name</Th>
                            <Th>Type</Th>
                            <Th>Size</Th>
                            <Th>Actions</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {directoryContents.map((item, index) => (
                            <Tr key={index}>
                              <Td>
                                <HStack>
                                  <Icon
                                    as={item.is_directory ? FiFolder : FiFile}
                                  />
                                  <Text>{item.name}</Text>
                                </HStack>
                              </Td>
                              <Td>
                                <Badge
                                  colorScheme={
                                    item.is_directory ? "purple" : "gray"
                                  }
                                >
                                  {item.is_directory ? "Directory" : "File"}
                                </Badge>
                              </Td>
                              <Td>
                                {item.is_directory
                                  ? "-"
                                  : `${(item.size / 1024).toFixed(1)} KB`}
                              </Td>
                              <Td>
                                {item.is_directory ? (
                                  <Button
                                    size="sm"
                                    onClick={() => loadDirectory(item.path)}
                                  >
                                    Open
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
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
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Command Runner Panel */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Card>
                  <CardHeader>
                    <Heading size="md">Command Execution</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4}>
                      <FormControl>
                        <FormLabel>Command</FormLabel>
                        <Input
                          value={command}
                          onChange={(e) => setCommand(e.target.value)}
                          placeholder="Enter command (e.g., npm, git, ls)"
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Arguments (space separated)</FormLabel>
                        <Input
                          value={commandArgs}
                          onChange={(e) => setCommandArgs(e.target.value)}
                          placeholder="install, status, -la, etc."
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Working Directory (optional)</FormLabel>
                        <Input
                          value={workingDir}
                          onChange={(e) => setWorkingDir(e.target.value)}
                          placeholder={
                            currentDirectory ||
                            "Leave empty for current directory"
                          }
                        />
                      </FormControl>

                      <Button
                        leftIcon={isExecuting ? <FiStopCircle /> : <FiPlay />}
                        onClick={executeCommand}
                        colorScheme="blue"
                        isLoading={isExecuting}
                        loadingText="Executing..."
                      >
                        Execute Command
                      </Button>
                    </VStack>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="md">Common Commands</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={{ base: 1, md: 2 }} spacing={3}>
                      {commonCommands.map((cmd, index) => (
                        <Button
                          key={index}
                          variant="outline"
                          justifyContent="flex-start"
                          onClick={() => {
                            setCommand(cmd.name.split(" ")[0]);
                            setCommandArgs(
                              cmd.name.split(" ").slice(1).join(" "),
                            );
                          }}
                        >
                          <VStack align="start" spacing={0}>
                            <Text fontWeight="medium">{cmd.name}</Text>
                            <Text fontSize="sm" color="gray.600">
                              {cmd.description}
                            </Text>
                          </VStack>
                        </Button>
                      ))}
                    </SimpleGrid>
                  </CardBody>
                </Card>

                {commandOutput && (
                  <Card>
                    <CardHeader>
                      <Heading size="md">Command Output</Heading>
                    </CardHeader>
                    <CardBody>
                      <Code
                        p={4}
                        borderRadius="md"
                        bg="gray.50"
                        color="gray.800"
                        display="block"
                        whiteSpace="pre-wrap"
                        fontSize="sm"
                      >
                        {commandOutput}
                      </Code>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>

            {/* Code Editor Panel */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Text fontWeight="medium">
                    {selectedFile
                      ? `Editing: ${selectedFile}`
                      : "No file selected"}
                  </Text>
                  <HStack>
                    <Button
                      leftIcon={<FiFile />}
                      onClick={openFile}
                      colorScheme="blue"
                    >
                      Open File
                    </Button>
                    {selectedFile && (
                      <Button
                        leftIcon={<FiSettings />}
                        onClick={saveFile}
                        colorScheme="green"
                      >
                        Save File
                      </Button>
                    )}
                  </HStack>
                </HStack>

                {selectedFile ? (
                  <Textarea
                    value={fileContent}
                    onChange={(e) => setFileContent(e.target.value)}
                    height="400px"
                    fontFamily="monospace"
                    fontSize="sm"
                    placeholder="File content will appear here..."
                  />
                ) : (
                  <Card>
                    <CardBody textAlign="center" py={10}>
                      <Icon as={FiFile} boxSize={12} color="gray.400" mb={4} />
                      <Text color="gray.600" mb={4}>
                        No file selected. Open a file to start editing.
                      </Text>
                      <Button
                        leftIcon={<FiFile />}
                        onClick={openFile}
                        colorScheme="blue"
                      >
                        Open File
                      </Button>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default DevTools;
