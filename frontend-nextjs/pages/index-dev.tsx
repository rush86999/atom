import config from "@config/config.json";
import Base from "@layouts/Baseof";
import Dashboard from "@components/Dashboard";
import { Box, VStack, Spinner, Text } from "@chakra-ui/react";
import { useEffect, useState } from "react";

const Home = () => {
  const { title } = config.site;
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <Base
        title={title}
        meta_title={undefined}
        description={undefined}
        image={undefined}
        noindex={undefined}
        canonical={undefined}
      >
        <Box p={8}>
          <VStack spacing={4} align="center">
            <Spinner size="xl" />
            <Text>Loading Atom...</Text>
          </VStack>
        </Box>
      </Base>
    );
  }

  return (
    <Base
      title={title}
      meta_title={undefined}
      description={undefined}
      image={undefined}
      noindex={undefined}
      canonical={undefined}
    >
      <Dashboard />
    </Base>
  );
};

export default Home;

export async function getServerSideProps() {
  // Development version - bypass SuperTokens authentication
  return {
    props: {
      sub: "dev-user-123",
      user: {
        id: "dev-user-123",
        email: "developer@example.com",
        name: "Development User",
      },
    },
  };
}
