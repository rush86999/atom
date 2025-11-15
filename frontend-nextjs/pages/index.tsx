import { getSession } from "next-auth/react";
import { GetServerSideProps } from "next";
import {
  Box,
  Container,
  VStack,
  Heading,
  Text,
  Button,
  Grid,
  GridItem,
  Card,
  CardBody,
  CardHeader,
  Icon,
  Flex,
} from "@chakra-ui/react";
import { useRouter } from "next/router";
import {
  FiSearch,
  FiMessageSquare,
  FiCheckSquare,
  FiPlay,
  FiCalendar,
  FiTerminal,
  FiServer,
} from "react-icons/fi";

export const getServerSideProps: GetServerSideProps = async (context) => {
  const session = await getSession(context);

  if (!session) {
    return {
      redirect: {
        destination: "/auth/signin",
        permanent: false,
      },
    };
  }

  return {
    props: {
      session,
    },
  };
};

const Home = () => {
  const router = useRouter();

  const features = [
    {
      title: "Search",
      description:
        "AI-powered search across all your documents, meetings, and notes",
      icon: FiSearch,
      path: "/search",
      color: "blue",
    },
    {
      title: "Communication",
      description: "Unified messaging hub for all your communication platforms",
      icon: FiMessageSquare,
      path: "/communication",
      color: "green",
    },
    {
      title: "Tasks",
      description: "Smart task management with AI-powered prioritization",
      icon: FiCheckSquare,
      path: "/tasks",
      color: "orange",
    },
    {
      title: "Workflow Automation",
      description: "Create and manage automated workflows across services",
      icon: FiPlay,
      path: "/automations",
      color: "purple",
    },
    {
      title: "Calendar",
      description: "Smart scheduling and calendar management",
      icon: FiCalendar,
      path: "/calendar",
      color: "red",
    },
    {
      title: "Dev Tools",
      description: "Development utilities and system integration",
      icon: FiTerminal,
      path: "/dev-tools",
      color: "purple",
    },
    {
      title: "Dev Status",
      description: "Development environment monitoring and status",
      icon: FiServer,
      path: "/dev-status",
      color: "teal",
    },
  ];

  return (
    <Container maxW="6xl" py={8}>
      <VStack spacing={8} align="stretch">
        <Box textAlign="center">
          <Heading size="2xl" mb={4}>
            Welcome to ATOM
          </Heading>
          <Text fontSize="xl" color="gray.600">
            Your AI-powered personal automation platform
          </Text>
        </Box>

        <Grid
          templateColumns={{
            base: "1fr",
            md: "repeat(2, 1fr)",
            lg: "repeat(3, 1fr)",
          }}
          gap={6}
        >
          {features.map((feature, index) => (
            <GridItem key={index}>
              <Card
                height="100%"
                cursor="pointer"
                _hover={{ transform: "translateY(-4px)", shadow: "lg" }}
                transition="all 0.2s"
                onClick={() => router.push(feature.path)}
              >
                <CardHeader>
                  <Flex align="center" gap={3}>
                    <Icon
                      as={feature.icon}
                      boxSize={6}
                      color={`${feature.color}.500`}
                    />
                    <Heading size="md">{feature.title}</Heading>
                  </Flex>
                </CardHeader>
                <CardBody>
                  <Text color="gray.600">{feature.description}</Text>
                </CardBody>
              </Card>
            </GridItem>
          ))}
        </Grid>

        <Box textAlign="center" mt={8}>
          <Text fontSize="lg" color="gray.600" mb={4}>
            Ready to automate your workflow?
          </Text>
          <Button
            colorScheme="blue"
            size="lg"
            onClick={() => router.push("/automations")}
          >
            Get Started with Automation
          </Button>
        </Box>
      </VStack>
    </Container>
  );
};

export default Home;
