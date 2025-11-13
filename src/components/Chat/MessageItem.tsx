#!/usr/bin/env node

/**
 * Atom Project - Phase 1: Chat Interface Foundation
 * Message Item Component Implementation

 * CRITICAL IMPLEMENTATION - Week 1
 * Priority: 🔴 HIGH
 * Objective: Build individual message display component
 * Timeline: 12 hours development + 4 hours testing

 * This component displays individual messages in the chat interface with
 * proper styling, metadata, status indicators, and interactive features.
 */

import * as React from 'react';
import { Box, VStack, HStack, Text, Avatar, IconButton, Menu, MenuButton, MenuList, MenuItem, Tooltip, useColorModeValue } from '@chakra-ui/react';
import { FiMoreVertical, FiEdit, FiCopy, FiTrash, FiReply, FiFlag, FiInfo, FiCheck, FiCheckCircle } from 'react-icons/fi';

import { ChatMessage } from '../../types/chat';

interface MessageItemProps {
  message: ChatMessage;
  isOwnMessage: boolean;
  showAvatar: boolean;
  showTimestamp: boolean;
  showStatus: boolean;
  onReply: (message: ChatMessage) => void;
  onEdit: (message: ChatMessage) => void;
  onDelete: (message: ChatMessage) => void;
  onFlag: (message: ChatMessage) => void;
  onCopy: (message: ChatMessage) => void;
  onViewDetails: (message: ChatMessage) => void;
  className?: string;
}

/**
 * Message Item Component
 * 
 * Displays individual messages with proper styling, metadata,
 * status indicators, and interactive features.
 */
export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  isOwnMessage,
  showAvatar,
  showTimestamp,
  showStatus,
  onReply,
  onEdit,
  onDelete,
  onFlag,
  onCopy,
  onViewDetails,
  className
}) => {
  const [isHovered, setIsHovered] = React.useState(false);
  const [showDetails, setShowDetails] = React.useState(false);

  // Color mode values
  const bgHover = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const subTextColor = useColorModeValue('gray.600', 'gray.400');

  // Format timestamp
  const formatTimestamp = React.useMemo(() => {
    return new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      month: 'short',
      day: 'numeric'
    }).format(new Date(message.timestamp));
  }, [message.timestamp]);

  // Get message status icon
  const getStatusIcon = React.useMemo(() => {
    switch (message.status) {
      case 'sending':
        return <FiCheck color="gray" size={12} />;
      case 'sent':
        return <FiCheck color="blue" size={12} />;
      case 'delivered':
        return <FiCheckCircle color="blue" size={12} />;
      case 'read':
        return <FiCheckCircle color="green" size={12} />;
      case 'error':
        return <FiInfo color="red" size={12} />;
      default:
        return null;
    }
  }, [message.status]);

  // Get message background color
  const getBackgroundColor = React.useMemo(() => {
    if (message.sender === 'system') {
      return useColorModeValue('yellow.50', 'yellow.900');
    }
    
    if (message.status === 'error') {
      return useColorModeValue('red.50', 'red.900');
    }
    
    return isOwnMessage 
      ? useColorModeValue('blue.500', 'blue.600')
      : useColorModeValue('gray.100', 'gray.700');
  }, [message.sender, message.status, isOwnMessage]);

  // Get text color
  const getTextColor = React.useMemo(() => {
    if (message.sender === 'system') {
      return useColorModeValue('yellow.800', 'yellow.100');
    }
    
    if (message.status === 'error') {
      return useColorModeValue('red.800', 'red.100');
    }
    
    return isOwnMessage 
      ? 'white'
      : textColor;
  }, [message.sender, message.status, isOwnMessage, textColor]);

  // Copy message to clipboard
  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      onCopy(message);
    } catch (error) {
      console.error('Failed to copy message:', error);
    }
  }, [message.content, onCopy]);

  // Render message content with markdown support (basic)
  const renderMessageContent = React.useMemo(() => {
    // Basic markdown support - can be enhanced later
    const content = message.content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/### (.*?)/g, '<h4>$1</h4>')
      .replace(/## (.*?)/g, '<h3>$1</h3>')
      .replace(/# (.*?)/g, '<h2>$1</h2>')
      .replace(/\n/g, '<br>');

    return (
      <Text
        fontSize="sm"
        color={getTextColor}
        whiteSpace="pre-wrap"
        wordBreak="break-word"
        className="message-content"
        dangerouslySetInnerHTML={{ __html: content }}
      />
    );
  }, [message.content, getTextColor]);

  return (
    <Box
      className={className}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      mb={3}
    >
      <HStack
        align="flex-start"
        justify={isOwnMessage ? 'flex-end' : 'flex-start'}
        spacing={3}
      >
        {/* Avatar */}
        {!isOwnMessage && showAvatar && (
          <Avatar
            size="sm"
            name={message.sender === 'ai' ? 'Atom AI' : 'User'}
            src={message.metadata?.avatar}
            bg={
              message.sender === 'ai' 
                ? 'blue.500' 
                : message.sender === 'system'
                ? 'yellow.500'
                : 'gray.500'
            }
            fallbackIcon={message.sender === 'ai' ? '🤖' : '👤'}
          />
        )}

        {/* Message Content */}
        <VStack
          maxW="70%"
          align={isOwnMessage ? 'flex-end' : 'flex-start'}
          spacing={1}
        >
          <HStack
            bg={getBackgroundColor}
            color={getTextColor}
            px={4}
            py={3}
            borderRadius="lg"
            borderTopLeftRadius={isOwnMessage ? 'lg' : 'none'}
            borderTopRightRadius={isOwnMessage ? 'none' : 'lg'}
            boxShadow="sm"
            position="relative"
            align="flex-start"
            spacing={2}
            onMouseEnter={() => setShowDetails(true)}
            onMouseLeave={() => setShowDetails(false)}
          >
            <Box flex={1}>
              {renderMessageContent}
              
              {/* Message metadata */}
              {(showDetails || showTimestamp) && (
                <VStack
                  align="flex-start"
                  spacing={1}
                  mt={2}
                  pt={2}
                  borderTopWidth="1px"
                  borderColor={useColorModeValue('gray.200', 'gray.600')}
                >
                  {/* Intent and entities (for AI messages) */}
                  {message.metadata?.intent && (
                    <HStack
                      flexWrap="wrap"
                      spacing={1}
                    >
                      <Text fontSize="xs" color={subTextColor}>
                        Intent:
                      </Text>
                      <Text
                        fontSize="xs"
                        bg="blue.100"
                        color="blue.800"
                        px={2}
                        py={1}
                        borderRadius="md"
                        fontWeight="medium"
                      >
                        {message.metadata.intent}
                      </Text>
                    </HStack>
                  )}

                  {/* Processing time */}
                  {message.metadata?.processing_time && (
                    <Text fontSize="xs" color={subTextColor}>
                      Processing: {message.metadata.processing_time}ms
                    </Text>
                  )}

                  {/* Error message */}
                  {message.metadata?.error && (
                    <Text fontSize="xs" color="red.600">
                      Error: {message.metadata.error}
                    </Text>
                  )}
                </VStack>
              )}
            </Box>

            {/* Actions menu */}
            {(isHovered || showDetails) && (
              <Menu>
                <MenuButton
                  as={IconButton}
                  icon={<FiMoreVertical />}
                  variant="ghost"
                  size="xs"
                  color={isOwnMessage ? 'white' : 'gray.500'}
                  _hover={{
                    bg: 'rgba(0,0,0,0.1)'
                  }}
                  position="absolute"
                  top={2}
                  right={2}
                />
                <MenuList>
                  <MenuItem
                    icon={<FiReply />}
                    onClick={() => onReply(message)}
                  >
                    Reply
                  </MenuItem>
                  
                  {isOwnMessage && message.status !== 'error' && (
                    <MenuItem
                      icon={<FiEdit />}
                      onClick={() => onEdit(message)}
                    >
                      Edit
                    </MenuItem>
                  )}
                  
                  <MenuItem
                    icon={<FiCopy />}
                    onClick={handleCopy}
                  >
                    Copy
                  </MenuItem>
                  
                  <MenuItem
                    icon={<FiInfo />}
                    onClick={() => onViewDetails(message)}
                  >
                    View Details
                  </MenuItem>
                  
                  <MenuItem
                    icon={<FiFlag />}
                    onClick={() => onFlag(message)}
                  >
                    Flag Message
                  </MenuItem>
                  
                  {isOwnMessage && (
                    <MenuItem
                      icon={<FiTrash />}
                      color="red.500"
                      onClick={() => onDelete(message)}
                    >
                      Delete
                    </MenuItem>
                  )}
                </MenuList>
              </Menu>
            )}
          </HStack>

          {/* Message footer */}
          <HStack
            justify="space-between"
            w="full"
            px={1}
            spacing={2}
          >
            <HStack spacing={1}>
              {/* Timestamp */}
              {showTimestamp && (
                <Text fontSize="xs" color={subTextColor}>
                  {formatTimestamp}
                </Text>
              )}

              {/* Edited indicator */}
              {message.metadata?.edited && (
                <Text fontSize="xs" color={subTextColor} fontStyle="italic">
                  (edited)
                </Text>
              )}
            </HStack>

            {/* Status indicator */}
            {isOwnMessage && showStatus && (
              <HStack spacing={1}>
                {getStatusIcon}
                
                {/* Status text */}
                <Text fontSize="xs" color={subTextColor}>
                  {message.status === 'sending' && 'Sending...'}
                  {message.status === 'sent' && 'Sent'}
                  {message.status === 'delivered' && 'Delivered'}
                  {message.status === 'read' && 'Read'}
                  {message.status === 'error' && 'Failed'}
                </Text>
              </HStack>
            )}
          </HStack>
        </VStack>

        {/* Avatar for own messages */}
        {isOwnMessage && showAvatar && (
          <Avatar
            size="sm"
            name="You"
            src={message.metadata?.userAvatar}
            bg="blue.500"
            fallbackIcon="👤"
          />
        )}
      </HStack>

      {/* Tooltip for message details */}
      {isHovered && message.metadata && (
        <Tooltip
          label={
            <VStack align="flex-start" spacing={1}>
              {message.metadata.agent && (
                <Text fontSize="xs">Agent: {message.metadata.agent}</Text>
              )}
              {message.metadata.confidence && (
                <Text fontSize="xs">
                  Confidence: {(message.metadata.confidence * 100).toFixed(1)}%
                </Text>
              )}
              {message.metadata.entities && message.metadata.entities.length > 0 && (
                <Text fontSize="xs">
                  Entities: {message.metadata.entities.length} found
                </Text>
              )}
            </VStack>
          }
          placement="top"
          bg={bgHover}
          borderRadius="md"
          p={2}
          boxShadow="md"
        />
      )}
    </Box>
  );
};

export default MessageItem;