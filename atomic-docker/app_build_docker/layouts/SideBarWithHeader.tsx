import React, { ReactNode } from "react";
import {
  IconButton,
  Avatar,
  Box,
  CloseButton,
  Flex,
  HStack,
  VStack,
  Icon,
  useColorModeValue,
  Link,
  Drawer,
  DrawerContent,
  Text,
  useDisclosure,
  BoxProps,
  FlexProps,
  Menu,
  MenuButton,
  MenuDivider,
  MenuItem,
  MenuList,
} from "@chakra-ui/react";
import {
  FiHome,
  FiTrendingUp,
  FiCompass,
  FiStar,
  FiSettings,
  FiMenu,
  FiBell,
  FiChevronDown,
  FiBriefcase,
  FiHelpCircle,
  // FiUnlock, // Not used
} from "react-icons/fi";
import { GiArtificialIntelligence } from "react-icons/gi";
import { ThemeToggleButton } from "@components/chat/ui/ThemeToggleButton"; // Import the new button
import { IconType } from "react-icons";
import { useUserRole } from "../contexts/userRole/userRoleContext";
import { ReactText } from "react";
import Logo from "@layouts/Logo";
import { signOut } from "supertokens-auth-react/recipe/thirdpartyemailpassword";
import Session from "supertokens-web-js/recipe/session";

interface LinkItemProps {
  name: string;
  icon: IconType;
  href: string;
}
import { FiDollarSign } from "react-icons/fi";

import { FaShoppingCart, FaSearch, FaFeatherAlt, FaGlobe } from "react-icons/fa";

const LinkItems: Array<LinkItemProps> = [
  { name: "Home", icon: FiHome, href: "/" },
  {
    name: "Meeting Assists",
    icon: GiArtificialIntelligence,
    href: "/Assist/UserListMeetingAssists",
  },
  { name: "Finance", icon: FiDollarSign, href: "/Finance" },
  { name: "Sales", icon: FiTrendingUp, href: "/Sales" },
  { name: "Projects", icon: FiBriefcase, href: "/Projects" },
  { name: "Support", icon: FiHelpCircle, href: "/Support" },
  { name: "Research", icon: FaSearch, href: "/Research" },
  { name: "Social", icon: FaGlobe, href: "/Social" },
  { name: "Content", icon: FaFeatherAlt, href: "/Content" },
  { name: "Shopping", icon: FaShoppingCart, href: "/Shopping" },
  { name: "Settings", icon: FiSettings, href: "/Settings" },
];

export default function SidebarWithHeader({
  children,
}: {
  children: ReactNode;
}) {
  const { isOpen, onOpen, onClose } = useDisclosure();
  return (
    <Box minH="100vh" bg={useColorModeValue("gray.100", "gray.900")}>
      <SidebarContent
        onClose={() => onClose}
        display={{ base: "none", md: "block" }}
      />
      <Drawer
        autoFocus={false}
        isOpen={isOpen}
        placement="left"
        onClose={onClose}
        returnFocusOnClose={false}
        onOverlayClick={onClose}
        size="full"
      >
        <DrawerContent>
          <SidebarContent onClose={onClose} />
        </DrawerContent>
      </Drawer>
      {/* mobilenav */}
      <MobileNav onOpen={onOpen} />
      <Box ml={{ base: 0, md: 60 }} p="4">
        {children}
      </Box>
    </Box>
  );
}

interface SidebarProps extends BoxProps {
  onClose: () => void;
}

const SidebarContent = ({ onClose, ...rest }: SidebarProps) => {
  const { hasRole } = useUserRole();

  return (
    <Box
      transition="3s ease"
      bg={useColorModeValue("white", "gray.900")}
      borderRight="1px"
      borderRightColor={useColorModeValue("gray.200", "gray.700")}
      w={{ base: "full", md: 60 }}
      pos="fixed"
      h="full"
      {...rest}
    >
      <Flex h="20" alignItems="center" mx="8" justifyContent="space-between">
        <Logo src={undefined} />
        <CloseButton display={{ base: "flex", md: "none" }} onClick={onClose} />
      </Flex>
      {LinkItems.filter((link) => {
        if (link.name === "Sales") {
          return hasRole("sales");
        }
        if (link.name === "Projects") {
          return hasRole("project_manager");
        }
        if (link.name === "Support") {
          return hasRole("support");
        }
        if (link.name === "Finance") {
            return hasRole("financial_analyst");
        }
        if (link.name === "Research") {
          return hasRole("researcher");
        }
        if (link.name === "Social") {
          return hasRole("social_media_manager");
        }
        if (link.name === "Content") {
          return hasRole("content_creator");
        }
        if (link.name === "Shopping") {
          return hasRole("shopper");
        }
        return true;
      }).map((link) => (
        <NavItem href={link.href} key={link.name} icon={link.icon}>
          {link.name}
        </NavItem>
      ))}
    </Box>
  );
};

interface NavItemProps extends FlexProps {
  icon: IconType;
  children: ReactText;
  href: string;
}
const NavItem = ({ icon, children, href, ...rest }: NavItemProps) => {
  return (
    <Link
      href={href}
      style={{ textDecoration: "none" }}
      _focus={{ boxShadow: "none" }}
    >
      <Flex
        align="center"
        p="4"
        mx="4"
        borderRadius="lg"
        role="group"
        cursor="pointer"
        _hover={{
          bg: "purple.400",
          color: "white",
        }}
        {...rest}
      >
        {icon && (
          <Icon
            mr="4"
            fontSize="16"
            _groupHover={{
              color: "white",
            }}
            as={icon}
          />
        )}
        {children}
      </Flex>
    </Link>
  );
};

interface MobileProps extends FlexProps {
  onOpen: () => void;
}
const MobileNav = ({ onOpen, ...rest }: MobileProps) => {
  return (
    <Flex
      ml={{ base: 0, md: 60 }}
      px={{ base: 4, md: 4 }}
      height="20"
      alignItems="center"
      bg={useColorModeValue("white", "gray.900")}
      borderBottomWidth="1px"
      borderBottomColor={useColorModeValue("gray.200", "gray.700")}
      justifyContent={{ base: "space-between", md: "flex-end" }}
      {...rest}
    >
      <IconButton
        display={{ base: "flex", md: "none" }}
        onClick={onOpen}
        variant="outline"
        aria-label="open menu"
        icon={<FiMenu />}
      />

      <Text
        display={{ base: "flex", md: "none" }}
        fontSize="2xl"
        fontFamily="monospace"
        fontWeight="bold"
      >
        Atomic
      </Text>

      <HStack spacing={{ base: "0", md: "6" }}>
        <ThemeToggleButton /> {/* Added ThemeToggleButton here */}
        <IconButton
          size="lg"
          variant="ghost"
          aria-label="open menu"
          icon={<FiBell />}
        />
        <Flex alignItems={"center"}>
          <Menu>
            <MenuButton
              py={2}
              transition="all 0.3s"
              _focus={{ boxShadow: "none" }}
            >
              <HStack>
                <Avatar size={"sm"} />
                <VStack
                  display={{ base: "none", md: "flex" }}
                  alignItems="flex-start"
                  spacing="1px"
                  ml="2"
                >
                  <Text fontSize="xs" color="gray.600">
                    User
                  </Text>
                </VStack>
                <Box display={{ base: "none", md: "flex" }}>
                  <FiChevronDown />
                </Box>
              </HStack>
            </MenuButton>
            <MenuList
              bg={useColorModeValue("white", "gray.900")}
              borderColor={useColorModeValue("gray.200", "gray.700")}
            >
              <MenuItem onClick={async () => signOut()}>Sign out</MenuItem>
            </MenuList>
          </Menu>
        </Flex>
      </HStack>
    </Flex>
  );
};
