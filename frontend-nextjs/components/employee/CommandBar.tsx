import React, { useState } from 'react';
import { Box, Input, InputGroup, Button } from '@chakra-ui/react';

interface CommandBarProps {
    onCommand: (command: string) => void;
    isLoading?: boolean;
}

export const CommandBar: React.FC<CommandBarProps> = ({ onCommand, isLoading }) => {
    const [command, setCommand] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (command.trim() && !isLoading) {
            onCommand(command);
            setCommand('');
        }
    };

    return (
        <Box 
            p={4} 
            bg={{ base: 'white', _dark: 'gray.800' }} 
            borderTop="1px solid" 
            borderColor={{ base: 'gray.200', _dark: 'gray.700' }}
            position="sticky"
            bottom={0}
            zIndex={10}
        >
            <form onSubmit={handleSubmit}>
                <InputGroup 
                    size="lg" 
                    width="100%"
                    endElement={
                        <Button 
                            h="1.75rem" 
                            size="sm" 
                            colorScheme="blue" 
                            type="submit"
                            isLoading={isLoading}
                            mr={1}
                        >
                            Run
                        </Button>
                    }
                >
                    <Input
                        placeholder="Type a task for your AI Employee... (e.g. 'Draft a market research report on AI trends')"
                        value={command}
                        onChange={(e) => setCommand(e.target.value)}
                        bg={{ base: 'gray.50', _dark: 'gray.900' }}
                        border="2px solid"
                        borderColor="transparent"
                        _focus={{ borderColor: 'blue.400' }}
                        disabled={isLoading}
                        pr="4.5rem"
                    />
                </InputGroup>
            </form>
        </Box>
    );
};

export default CommandBar;
