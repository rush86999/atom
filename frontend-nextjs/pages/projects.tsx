import React from 'react';
import { Box } from '@chakra-ui/react';
import KanbanBoard from '../components/Projects/KanbanBoard';

const Projects = () => {
    return (
        <Box p={8}>
            <KanbanBoard />
        </Box>
    );
};

export default Projects;
