import React from 'react';
import { Box, Text, Textarea, Flex, Button } from '@chakra-ui/react';

interface EditorProps {
    content: string;
    onSave: (content: string) => void;
    title?: string;
}

export const Editor: React.FC<EditorProps> = ({ content, onSave, title = 'New Artifact' }) => {
    const [localContent, setLocalContent] = React.useState(content);

    React.useEffect(() => {
        setLocalContent(content);
    }, [content]);

    return (
        <Box
            height="100%"
            display="flex"
            flexDirection="column"
            bg={{ base: 'white', _dark: 'gray.900' }}
            border="1px solid"
            borderColor={{ base: 'gray.200', _dark: 'gray.700' }}
            borderRadius="md"
            overflow="hidden"
            boxShadow="sm"
        >
            <Flex
                p={3}
                borderBottom="1px solid"
                borderColor={{ base: 'gray.200', _dark: 'gray.700' }}
                justify="space-between"
                align="center"
                bg={{ base: 'gray.50', _dark: 'gray.800' }}
            >
                <Text fontWeight="bold" fontSize="sm">{title}</Text>
                <Button
                    size="xs"
                    colorScheme="blue"
                    onClick={() => onSave(localContent)}
                >
                    Save
                </Button>
            </Flex>
            <Box flex={1} p={4}>
                <Textarea
                    value={localContent}
                    onChange={(e) => setLocalContent(e.target.value)}
                    height="100%"
                    variant="unstyled"
                    placeholder="Start writing..."
                    resize="none"
                    fontFamily="mono"
                    fontSize="sm"
                />
            </Box>
        </Box>
    );
};

export default Editor;
